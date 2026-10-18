"""Percorre as sete superfícies ASCOM com criação, erro, edição e cancelamento reais."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from playwright.sync_api import expect

from gestao.cadastros.models import Servidor
from gestao.identidade.models import Usuario

from .conftest import estabilizar, rodar_axe

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.django_db(transaction=True)]

RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIAS = RAIZ / "docs" / "auditorias" / "cadastros-compartilhados" / "ascom-capturas"


def _catalogos():
    from gestao.imprensa.models import Integrante as IntegranteImprensa
    from gestao.imprensa.models import Veiculo
    from gestao.palestras.models import Palestrante, RespostaPadrao, Tema
    from gestao.publicacoes.models import Integrante as IntegrantePublicacoes
    from gestao.publicacoes.models import UnidadeResponsavel

    return [
        ("palestras:palestrantes", Palestrante, "nome"),
        ("imprensa:equipe", IntegranteImprensa, "nome"),
        ("imprensa:veiculos", Veiculo, "nome"),
        ("publicacoes:equipe", IntegrantePublicacoes, "nome"),
        ("publicacoes:unidades", UnidadeResponsavel, "nome"),
        ("palestras:temas", Tema, "nome"),
        ("palestras:respostas", RespostaPadrao, "tipo"),
    ]


def _sem_corte(pg):
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    controles = pg.locator("main input:not([type=hidden]), main textarea, main button:visible")
    for elemento in controles.all():
        caixa = elemento.bounding_box()
        if caixa and elemento.is_visible():
            assert caixa["x"] >= -1
            assert caixa["x"] + caixa["width"] <= pg.viewport_size["width"] + 1


def _capturar(pg, caminho):
    posicao = pg.evaluate("[scrollX, scrollY]")
    pg.evaluate("window.scrollTo(0, 0)")
    estabilizar(pg)
    pg.screenshot(path=str(caminho), full_page=True, animations="disabled")
    pg.evaluate("([x, y]) => window.scrollTo(x, y)", posicao)
    estabilizar(pg)


@pytest.mark.parametrize("largura", [360, 1440])
def test_sete_cadastros_ascom(navegador, live_server, largura):
    gestor = Usuario.objects.create_superuser("ascom-visual", "ascom@teste.invalid", None,
                                              nome="Gestor da ASCOM")
    cliente = Client()
    cliente.force_login(gestor)
    catalogos = _catalogos()
    filtro_catalogo = os.environ.get("ASCOM_CATALOGO", "")
    if filtro_catalogo:
        catalogos = [cat for cat in catalogos if cat[0] == filtro_catalogo]
        assert catalogos, "ASCOM_CATALOGO deve identificar uma rota inventariada."
    prefixo_relatorio = filtro_catalogo.replace(":", "-") + "-" if filtro_catalogo else ""
    Servidor.objects.bulk_create([Servidor(nome=f"Servidor sintético {i:03d}")
                                  for i in range(25)])
    servidor = Servidor.objects.create(nome="ZZZ Pessoa encontrada pela busca remota")
    for _, modelo, campo in catalogos:
        modelo.objects.bulk_create([modelo(**{campo: f"Cadastro sintético com nome longo {i:02d}"})
                                    for i in range(29)])
    contexto = navegador.new_context(viewport={"width": largura, "height": 900},
                                     locale="pt-BR", timezone_id="America/Sao_Paulo",
                                     reduced_motion="reduce")
    contexto.add_cookies([{"name": settings.SESSION_COOKIE_NAME,
                           "value": cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                           "domain": urlsplit(live_server.url).hostname, "path": "/"}])
    pg = contexto.new_page()
    erros = []
    pg.on("pageerror", lambda erro: erros.append({"url": pg.url, "erro": str(erro),
                                                "stack": erro.stack}))
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    cobertura = []
    try:
        for nome_url, modelo, campo in catalogos:
            url = live_server.url + reverse(nome_url)
            nome = nome_url.replace(":", "-")
            pg.goto(url)
            estabilizar(pg)
            expect(pg.locator("h1")).to_be_visible()
            expect(pg.locator("li.registro")).to_have_count(25)
            _sem_corte(pg)
            _capturar(pg, EVIDENCIAS / f"{nome}-{largura}-lista.png")
            pg.evaluate("window.scrollTo(0, 0)")
            estabilizar(pg)
            violacoes_iniciais = rodar_axe(pg)
            assert not violacoes_iniciais, [(v["id"], [n["target"] for n in v["nodes"]])
                                            for v in violacoes_iniciais]

            # Busca e inclusão funcionam também só por teclado (Enter).
            pg.locator("#busca-cadastro").fill("não existe esse nome")
            pg.locator("#busca-cadastro").press("Enter")
            expect(pg.get_by_text("Nenhum resultado", exact=True)).to_be_visible()
            pg.get_by_role("link", name="Limpar busca").click()
            pg.get_by_role("link", name="Próxima página").click()
            expect(pg.locator("li.registro")).to_have_count(4)
            pg.goto(url)
            novo = pg.locator("section[aria-labelledby='t-novo'] form")
            novo.locator(f"[name='{campo}']").fill("")
            novo.get_by_role("button", name="Incluir", exact=True).click()
            expect(pg.locator(".campo__erro, .alerta--perigo").first).to_be_visible()
            novo = pg.locator("section[aria-labelledby='t-novo'] form")
            titulo = f"Cadastro de validação com nome extenso da assessoria {largura}"
            novo.locator(f"[name='{campo}']").fill(titulo)
            if nome_url.endswith(":palestrantes"):
                seletor_servidor = novo.locator("pc-combobox").filter(
                    has=pg.locator("select[name='servidor']"))
                seletor_servidor.get_by_role("combobox").fill("Pessoa encontrada")
                seletor_servidor.get_by_role("option", name=servidor.nome, exact=True).click()
                expect(novo.locator("select[name='servidor']")).to_have_value(str(servidor.pk))
            if campo == "tipo":
                novo.locator("[name=mensagem]").fill("Olá {solicitante}, retornaremos em {data}.")
            novo.get_by_role("button", name="Incluir", exact=True).click()
            criado = modelo.objects.get(**{campo: titulo})
            if nome_url.endswith(":palestrantes"):
                assert criado.servidor_id == servidor.pk
                Servidor.objects.filter(pk=servidor.pk).update(ativo=False)
            pg.locator("#busca-cadastro").fill("Cadastro de validação")
            pg.locator("#busca-cadastro").press("Enter")
            expect(pg.locator("li.registro")).to_have_count(1)
            linha = pg.locator("li.registro").first
            if nome_url.endswith(":palestrantes"):
                linha.get_by_role("link", name=re.compile("Editar")).click()
            else:
                linha.locator("summary").focus()
                linha.locator("summary").press("Enter")
            linha = pg.locator("li.registro").first
            editar = linha.locator("form").first
            seletor = f"[name='p{criado.pk}-nome']" if nome_url.endswith(":palestrantes") else f"[name='{campo}']"
            editar.locator(seletor).fill("")
            editar.get_by_role("button", name="Salvar", exact=True).click()
            linha = pg.locator("li.registro").first
            expect(linha.locator(".campo__erro").first).to_be_visible()
            estabilizar(pg)
            _sem_corte(pg)
            _capturar(pg, EVIDENCIAS / f"{nome}-{largura}-erro.png")
            # Audita o documento inteiro com erro em um ponto reproduzível. Uma rolagem
            # arbitrária pode deixar controles anteriores parcialmente sob o shell fixo.
            # A edição permanece no DOM e a captura full_page mostra todos os campos.
            pg.evaluate("window.scrollTo(0, 0)")
            estabilizar(pg)
            violacoes = rodar_axe(pg)
            (EVIDENCIAS / f"{nome}-{largura}-axe.json").write_text(
                json.dumps(violacoes, ensure_ascii=False, indent=2), encoding="utf-8")
            if violacoes:
                alvos = [alvo for v in violacoes for n in v["nodes"] for alvo in n["target"]]
                geometria = pg.evaluate("""seletores => ({scrollY, innerWidth, innerHeight,
                    alvos: seletores.map(seletor => {
                        const el = document.querySelector(seletor);
                        if (!el) return {seletor, ausente: true};
                        const r = el.getBoundingClientRect(), css = getComputedStyle(el);
                        return {seletor, caixa: r.toJSON(), estilo: {width: css.width,
                            height: css.height, position: css.position, zIndex: css.zIndex},
                            pontos: [r.top + 2, r.top + r.height / 2, r.bottom - 2].map(y => {
                                const encontrado = document.elementFromPoint(r.left + r.width / 2, y);
                                return {y, elemento: encontrado?.outerHTML.slice(0, 500)};
                            })};
                    })})""", alvos)
                (EVIDENCIAS / f"{nome}-{largura}-geometria.json").write_text(
                    json.dumps(geometria, ensure_ascii=False, indent=2), encoding="utf-8")
                pg.screenshot(path=str(EVIDENCIAS / f"{nome}-{largura}-alvos.png"),
                              animations="disabled")
            assert not violacoes, [(v["id"], [n["target"] for n in v["nodes"]])
                                   for v in violacoes]
            editar = linha.locator("form").first
            revisado = f"Cadastro de validação revisado com nome longo {largura}"
            editar.locator(seletor).fill(revisado)
            editar.get_by_role("button", name="Salvar", exact=True).click()
            criado.refresh_from_db()
            assert getattr(criado, campo) == revisado
            if nome_url.endswith(":palestrantes"):
                assert criado.servidor_id == servidor.pk
            linha = pg.locator("li.registro").first
            if nome_url.endswith(":palestrantes"):
                linha.get_by_role("link", name=re.compile("Editar")).click()
            else:
                linha.locator("summary").click()
            editar = pg.locator("li.registro form").first
            editar.locator(seletor).fill("Alteração cancelada")
            editar.get_by_role("link", name="Cancelar", exact=True).click()
            criado.refresh_from_db()
            assert getattr(criado, campo) == revisado
            estabilizar(pg)
            _sem_corte(pg)
            _capturar(pg, EVIDENCIAS / f"{nome}-{largura}-salvo.png")
            cobertura.append({"rota": reverse(nome_url), "largura": largura,
                               "criar": True, "editar": True, "validar": True,
                               "cancelar": True, "teclado": True, "busca": True,
                               "paginacao": True, "axe_violacoes": len(violacoes)})
        assert not erros, erros
    finally:
        (EVIDENCIAS / f"erros-js-{prefixo_relatorio}{largura}.json").write_text(
            json.dumps(erros, ensure_ascii=False, indent=2), encoding="utf-8")
        (EVIDENCIAS / f"cobertura-{prefixo_relatorio}{largura}.json").write_text(
            json.dumps(cobertura, ensure_ascii=False, indent=2), encoding="utf-8")
        contexto.close()
