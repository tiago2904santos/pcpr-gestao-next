"""Cobertura visual do inventário em LAB sintético, com medidas reproduzíveis."""

import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import expect

from .conftest import entrar, estabilizar, rodar_axe

pytestmark = pytest.mark.e2e
DESTINO = Path("docs/auditorias/cadastros-compartilhados/evidencias")


def _rotas():
    from gestao.eventos.catalogos import CATALOGOS

    simples = ["unidades", "cargos", "combustiveis", "tipos-de-viagem", "programas",
               "horarios", "atividades", "conjuntos"]
    rotas = [f"/cadastros/{s}/" for s in ["servidores", "viaturas", *simples,
             "diarias", "textos-prontos", "usuarios", "configuracao"]]
    rotas += [f"/eventos/cadastros/{s}/" for s in CATALOGOS]
    rotas += [f"/coffee/cadastros/{s}/" for s in
              ["fornecedores", "contratos", "aditivos", "lotes", "oficio"]]
    rotas += [f"/palestras/cadastros/{s}/" for s in ["palestrantes", "temas", "respostas"]]
    rotas += [f"/imprensa/cadastros/{s}/" for s in ["equipe", "veiculos"]]
    rotas += [f"/publicacoes/cadastros/{s}/" for s in ["equipe", "unidades"]]
    return rotas


@pytest.mark.parametrize("largura", [360, 1440])
def test_inventario_listas_e_modais(pagina, dados_e2e, largura):
    usuario = dados_e2e.usuarios["operador"]
    usuario.is_superuser = True
    usuario.save(update_fields=["is_superuser"])
    pg = pagina
    entrar(pg)
    pg.emulate_media(reduced_motion="reduce")
    pg.set_viewport_size({"width": largura, "height": 900})
    fase = os.environ.get("CADASTROS_FASE", "depois")
    pasta = DESTINO / fase / str(largura)
    pasta.mkdir(parents=True, exist_ok=True)
    medidas = []
    for rota in _rotas():
        resposta = pg.goto(rota)
        assert resposta and resposta.ok, rota
        estabilizar(pg)
        nome = rota.strip("/").replace("/", "-")
        pg.screenshot(path=str(pasta / f"{nome}.png"), full_page=True)
        excesso = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
        assert excesso <= 1, (rota, excesso)
        medidas.append({"rota": rota, "largura": largura, "overflow": excesso,
                        "html_bytes": len(pg.content().encode()), "superficie": "lista"})
        abrir = pg.locator("main [data-abrir-dialogo]").first
        if abrir.count():
            abrir.click()
            janela = pg.locator("dialog:modal").last
            if janela.count():
                estabilizar(pg)
                pg.screenshot(path=str(pasta / f"{nome}-modal.png"))
                assert not janela.evaluate("e => e.scrollWidth > e.clientWidth + 1"), rota
                if fase != "antes":
                    assert rodar_axe(pg) == [], rota
                medidas.append({"rota": rota, "largura": largura,
                                "superficie": "modal", "largura_modal":
                                janela.evaluate("e => Math.round(e.getBoundingClientRect().width)")})
                pg.keyboard.press("Escape")
    (pasta / "medidas.json").write_text(json.dumps(medidas, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    assert not pg.erros_console


@pytest.mark.parametrize("largura", [360, 1440])
def test_cadastro_rapido_retorna_sem_empilhar_ou_perder_dados(logado, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 650})
    pg.goto("/cadastros/servidores/")
    pg.get_by_role("button", name="Novo servidor", exact=True).first.click()
    pai = pg.locator("#dialogo-servidor")
    nome = pai.get_by_label("Nome completo")
    nome.fill("Pessoa com nome extenso preservado durante o cadastro auxiliar")
    origem = pai.get_by_role("button", name="Cadastrar cargo", exact=True)
    origem.click()
    auxiliar = pg.locator("#dialogo-cargo")
    expect(auxiliar).to_be_visible()
    expect(pg.locator("dialog:modal")).to_have_count(1)
    auxiliar.get_by_role("button", name="Cadastrar cargo", exact=True).click()
    expect(auxiliar.locator("[data-erro]")).to_be_visible()
    auxiliar.locator('input[name="nome"]').fill(f"Cargo compartilhado da missão {largura}")
    auxiliar.get_by_role("button", name="Cadastrar cargo", exact=True).click()
    expect(auxiliar).to_be_hidden()
    expect(pai).to_be_visible()
    expect(nome).to_have_value("Pessoa com nome extenso preservado durante o cadastro auxiliar")
    expect(origem).to_be_focused()
    expect(pai.locator("select[name=cargo] option:checked")).to_contain_text("Cargo Compartilhado")
    rodape = pai.locator(".dialogo__rodape")
    caixa = rodape.bounding_box()
    assert caixa and caixa["y"] >= 0 and caixa["y"] + caixa["height"] <= 650
    pai.locator(".dialogo__corpo").evaluate("e => e.scrollTop = e.scrollHeight")
    caixa_final = rodape.bounding_box()
    assert caixa_final and abs(caixa_final["y"] - caixa["y"]) < 1
    pg.keyboard.press("Escape")
    expect(pai).to_be_hidden()
    # O envio vazio acima provoca deliberadamente um único HTTP 422.
    assert len(pg.erros_console) == 1 and "422" in pg.erros_console[0]


@pytest.mark.parametrize("largura", [360, 1440])
def test_catalogo_unico_em_planos_e_eventos(pagina, dados_e2e, largura):
    from django.urls import reverse

    from gestao.cadastros.models import AtividadePlano
    from gestao.eventos.models import Solicitacao
    from gestao.viagens.models import PlanoTrabalho

    usuario = dados_e2e.usuarios["operador"]
    usuario.is_superuser = True
    usuario.save(update_fields=["is_superuser"])
    pg = pagina
    entrar(pg)
    pg.set_viewport_size({"width": largura, "height": 900})
    nome = f"Atendimento compartilhado da missão {largura}"
    pg.goto("/eventos/cadastros/servicos/")
    pg.locator("main [data-abrir-dialogo=dialogo-cadastro]").first.click()
    pg.locator("#cadastro-nome").fill(nome)
    pg.locator("#dialogo-cadastro button[type=submit]").click()
    expect(pg.locator(".registros")).to_contain_text(nome, ignore_case=True)
    item = AtividadePlano.objects.get(nome__iexact=nome)
    quantidade = AtividadePlano.objects.count()
    plano = PlanoTrabalho.objects.create(unidade=usuario.lotacao.unidade, ano=2026,
                                          numero=9001, criado_por=usuario)
    pg.goto(reverse("viagens:editar_plano", args=[plano.pk]))
    atividade = pg.get_by_role("checkbox", name=nome, exact=True)
    atividade.focus()
    atividade.press("Space")
    expect(atividade).to_be_checked()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo", timeout=15000)
    assert plano.atividades.get().pk == item.pk
    pedido = Solicitacao.objects.create(criado_por=usuario, data_solicitacao=date(2026, 10, 17))
    pg.goto(reverse("eventos:solicitacao", args=[pedido.pk]))
    pg.get_by_label(nome, exact=True).check()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo", timeout=15000)
    assert pedido.servicos.get().servico_id == item.pk
    pg.goto(f"/cadastros/atividades/?editar={item.pk}")
    modal = pg.locator("#dialogo-cadastro")
    revisado = nome + " revisado"
    modal.locator('[name="nome"]').fill(revisado)
    modal.locator('[name="meta"]').fill("Atender com informação clara.")
    modal.get_by_role("button", name="Salvar alterações", exact=True).click()
    expect(pg.locator(".registros")).to_contain_text(revisado, ignore_case=True)
    item.refresh_from_db()
    revisado = item.nome
    pg.goto(f"/eventos/cadastros/servicos/?q={quote(revisado)}")
    pg.locator(".registro").filter(has_text=revisado).locator("[data-menu-botao]").click()
    pg.get_by_role("menuitem", name="Desativar", exact=True).click()
    expect(pg.get_by_role("heading", name="Nenhum registro encontrado")).to_be_visible()
    item.refresh_from_db()
    assert not item.ativo
    assert plano.atividades.get().pk == pedido.servicos.get().servico_id == item.pk
    assert str(pedido.servicos.get()) == nome
    assert AtividadePlano.objects.count() == quantidade
    pg.goto(reverse("viagens:novo_plano"))
    expect(pg.get_by_role("checkbox", name=revisado, exact=True)).to_have_count(0)
    pg.goto(reverse("eventos:nova"))
    expect(pg.get_by_label(revisado, exact=True)).to_have_count(0)
    pg.goto(reverse("viagens:editar_plano", args=[plano.pk]) + "?evento=novo")
    evento = pg.locator("#dialogo-evento")
    expect(evento).to_be_visible()
    estabilizar(pg)
    texto_cabecalho = evento.locator(".dialogo__cabecalho-texto").bounding_box()
    fechar = evento.get_by_role("link", name="Fechar", exact=True).bounding_box()
    assert texto_cabecalho and fechar
    assert texto_cabecalho["x"] + texto_cabecalho["width"] <= fechar["x"]
    pasta = DESTINO / "consumidores" / str(largura)
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / "plano-evento-modal.png"))
    assert not evento.evaluate("e => e.scrollWidth > e.clientWidth + 1")
    assert rodar_axe(pg) == []
    evento.get_by_role("button", name="Cadastrar horário", exact=True).click()
    expect(pg.locator("dialog:modal")).to_have_count(1)
    pg.keyboard.press("Escape")
    expect(evento).to_be_visible()
    assert not pg.erros_console


def test_cadastro_rapido_incluir_outro_mantem_etapa(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    pg.get_by_role("button", name="Cadastrar servidor", exact=True).click()
    janela = pg.locator("#dialogo-servidor")
    nome = janela.get_by_label("Nome completo")
    nome.fill("Pessoa sintética para inclusão em sequência")
    janela.get_by_role("button", name="Cadastrar e incluir outro", exact=True).click()
    expect(janela).to_be_visible()
    expect(nome).to_have_value("")
    expect(nome).to_be_focused()
    expect(pg.locator("#equipe")).to_contain_text(
        "Pessoa sintética para inclusão em sequência", ignore_case=True)
    janela.get_by_role("button", name="Cancelar", exact=True).click()
    expect(janela).to_be_hidden()
    assert not pg.erros_console


@pytest.mark.parametrize("largura", [360, 1440])
def test_seis_catalogos_eventos_fluxos_completos(pagina, dados_e2e, largura):
    from gestao.eventos.catalogos import CATALOGOS

    usuario = dados_e2e.usuarios["operador"]
    usuario.is_superuser = True
    usuario.save(update_fields=["is_superuser"])
    pg = pagina
    entrar(pg)
    pg.emulate_media(reduced_motion="reduce")
    pg.set_viewport_size({"width": largura, "height": 900})
    for slug, catalogo in CATALOGOS.items():
        pg.goto(f"/eventos/cadastros/{slug}/")
        janela = pg.locator("#dialogo-cadastro")
        pg.locator("main [data-abrir-dialogo=dialogo-cadastro]").first.click()
        expect(janela).to_be_visible()
        janela.locator("button[type=submit]").click()  # vazio: volta com o erro no campo
        expect(janela).to_be_visible()
        expect(pg.locator("#cadastro-nome")).to_have_attribute("aria-invalid", "true")
        nome = f"Registro sintético com nome representativo {slug} {largura}"
        pg.locator("#cadastro-nome").fill(nome)
        if catalogo.com_texto:
            janela.locator("[name=texto]").fill("Texto do despacho preservado após a validação.")
        janela.locator("button[type=submit]").click()
        linha = pg.locator(".registro").filter(has_text=nome)
        expect(linha).to_be_visible()
        objeto = catalogo.modelo.objects.get(nome=nome)
        linha.locator(".registro__link").click()  # editar e desistir não altera nada
        expect(janela).to_be_visible()
        pg.locator("#cadastro-nome").fill("Alteração cancelada")
        janela.get_by_role("link", name="Cancelar", exact=True).click()
        expect(janela).to_be_hidden()
        objeto.refresh_from_db()
        assert objeto.nome == nome
        linha.locator(".registro__link").click()
        pg.locator("#cadastro-nome").fill("")
        janela.get_by_role("button", name="Salvar alterações", exact=True).click()
        expect(pg.locator("#cadastro-nome")).to_have_attribute("aria-invalid", "true")
        revisado = nome + " revisado"
        pg.locator("#cadastro-nome").fill(revisado)
        janela.get_by_role("button", name="Salvar alterações", exact=True).click()
        linha = pg.locator(".registro").filter(has_text=revisado)
        expect(linha).to_be_visible()
        objeto.refresh_from_db()
        assert objeto.nome == revisado
        linha.locator("[data-menu-botao]").click()
        pg.get_by_role("menuitem", name="Desativar", exact=True).click()
        expect(linha).to_have_count(0)
        objeto.refresh_from_db()
        assert not objeto.ativo
        pg.goto(f"/eventos/cadastros/{slug}/?aba=inativos&q={quote(revisado)}")
        linha.locator("[data-menu-botao]").click()
        pg.get_by_role("menuitem", name="Reativar", exact=True).click()
        expect(pg.get_by_role("heading", name="Nenhum registro encontrado")).to_be_visible()
        objeto.refresh_from_db()
        assert objeto.ativo
        assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        pg.evaluate("window.scrollTo(0, 0)")
        assert rodar_axe(pg) == []
    # Os dois envios vazios de cada catálogo (criar e editar) provocam de propósito um
    # HTTP 422 cada; nenhum outro erro no console.
    assert len(pg.erros_console) == 2 * len(CATALOGOS)  # type: ignore[attr-defined]
    assert all("422" in e for e in pg.erros_console)  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_termo_aditivo_coffee_criacao_erro_edicao_cancelamento(pagina, dados_e2e, largura):
    from decimal import Decimal

    from gestao.coffee.models import Contrato, Fornecedor, TermoAditivo

    usuario = dados_e2e.usuarios["operador"]
    usuario.is_superuser = True
    usuario.save(update_fields=["is_superuser"])
    fornecedor = Fornecedor.objects.create(razao_social="Fornecedor sintético da missão")
    Contrato.objects.create(fornecedor=fornecedor, numero="Base da missão",
                             valor_unitario=Decimal("20"))
    pg = pagina
    entrar(pg)
    pg.emulate_media(reduced_motion="reduce")
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/coffee/cadastros/aditivos/?novo=1")
    janela = pg.locator("#dialogo-cadastro")
    janela.get_by_role("button", name="Salvar", exact=True).click()
    expect(janela.locator(".campo__erro").first).to_be_visible()
    janela.get_by_role("combobox", name="Contrato", exact=True).click()
    pg.get_by_role("option", name="Contrato Base da missão · Fornecedor sintético da missão").click()
    janela.locator("[name=numero]").fill("5/2026")
    janela.get_by_role("button", name="Salvar", exact=True).click()
    expect(pg.locator(".registros")).to_contain_text("5/2026")
    termo = TermoAditivo.objects.get(numero="5/2026")
    pg.locator(".registro__link").first.click()
    janela.locator("[name=numero]").fill("6/2026")
    janela.get_by_role("button", name="Salvar", exact=True).click()
    termo.refresh_from_db()
    assert termo.numero == "6/2026" and TermoAditivo.objects.count() == 1
    pg.locator(".registro__link").first.click()
    janela.locator("[name=numero]").fill("Alteração cancelada")
    janela.get_by_role("link", name="Cancelar", exact=True).click()
    termo.refresh_from_db()
    assert termo.numero == "6/2026"
    pg.goto("/coffee/cadastros/contratos/?novo=1")
    expect(janela).to_be_visible()
    estabilizar(pg)
    pasta = DESTINO / "consumidores" / str(largura)
    pasta.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(pasta / "coffee-contrato-grupos.png"))
    assert rodar_axe(pg) == []
    assert len(pg.erros_console) == 1 and "422" in pg.erros_console[0]


@pytest.mark.parametrize("largura", [360, 1440])
def test_certidao_coffee_modal_e_calendario(logado, largura):
    from gestao.coffee.models import Certidao

    from .test_coffee import _lote_de_curitiba, _operador_do_modulo

    _operador_do_modulo()
    lote = _lote_de_curitiba()
    fornecedor = lote.contrato.fornecedor
    fornecedor.razao_social = "Fornecedor sintético com identificação extensa para conferência"
    fornecedor.save(update_fields=["razao_social"])
    pg = logado
    pg.emulate_media(reduced_motion="reduce")
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/coffee/certidoes/")
    pg.locator('a[href^="?anexar="]').first.click()
    janela = pg.locator("#dialogo-certidao")
    expect(janela).to_be_visible()
    expect(janela.get_by_role("heading")).to_contain_text(fornecedor.razao_social)
    janela.get_by_label("Válida até", exact=True).fill("17/11/2030")
    janela.get_by_role("button", name="Conferir e anexar", exact=True).click()
    expect(pg.locator(".toast")).to_contain_text("escolha o PDF")
    expect(janela).to_be_visible()
    expect(janela.get_by_role("alert")).to_contain_text("escolha o PDF")
    expect(janela.get_by_label("Válida até", exact=True)).to_have_value("17/11/2030")
    calendario = janela.get_by_role("button", name="Escolher data: Válida até", exact=True)
    calendario.click()
    expect(pg.locator(".calendario:visible")).to_be_visible()
    estabilizar(pg)
    pasta = DESTINO / "consumidores" / str(largura)
    pasta.mkdir(parents=True, exist_ok=True)
    limites = pg.locator(".calendario:visible").evaluate(
        """e => {const r=e.getBoundingClientRect(), s=getComputedStyle(e);
            return {top:r.top, bottom:r.bottom, altura:e.offsetHeight, viewport:innerHeight,
                cssTop:s.top, cssBottom:s.bottom, popover:e.matches(':popover-open')};} """)
    (pasta / "coffee-calendario-limites.json").write_text(
        json.dumps(limites, indent=2), encoding="utf-8")
    pg.screenshot(path=str(pasta / "coffee-certidao-calendario.png"))
    assert limites["top"] >= 0 and limites["bottom"] <= limites["viewport"], limites
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    expect(janela).to_be_visible()
    assert not janela.evaluate("e => e.scrollWidth > e.clientWidth + 1")
    assert rodar_axe(pg) == []
    pg.screenshot(path=str(pasta / "coffee-certidao-modal.png"))
    janela.get_by_role("link", name="Cancelar", exact=True).click()
    expect(janela).to_have_count(0)
    assert Certidao.objects.count() == 0
    assert not pg.erros_console
