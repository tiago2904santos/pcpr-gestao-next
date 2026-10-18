"""Preparação de Planos: quantitativos, calendário, evento e geração reais."""

import json
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Servidor
from gestao.viagens import planos
from gestao.viagens.tests.test_planos import _completo
from tests.e2e.conftest import rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 1440])
def test_cargo_acompanha_escolha_e_limpeza_do_coordenador(logado, dados_e2e, largura):
    pg = logado
    servidor = Servidor.objects.filter(unidade__sigla="ASCOM", cargo__isnull=False).first()
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto("/viagens/planos/novo/")
    for tipo in ("adm", "op"):
        campo = pg.locator(f"#busca-coord-{tipo}")
        ajuda = pg.locator(f"#busca-coord-{tipo}-ajuda")
        campo.fill(servidor.nome)
        pg.get_by_role("option").filter(has_text=servidor.nome).first.click()
        expect(ajuda.locator("[data-meta-escolhida]")).to_have_text(servidor.cargo.nome)
        expect(ajuda.locator("[data-meta-escolhida]")).to_be_visible()
        expect(ajuda.locator(".coordenador__orientacao")).not_to_be_visible()
        campo.fill("")
        expect(ajuda.locator("[data-meta-escolhida]")).not_to_be_visible()
        expect(ajuda.locator(".coordenador__orientacao")).to_be_visible()
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert pg.erros_console == []


def test_cadastro_rapido_de_conjunto_preserva_plano(logado, dados_e2e):
    pg = logado
    plano = _completo(dados_e2e)
    atividades = set(plano.atividades.values_list("pk", flat=True))
    pg.goto(f"/viagens/planos/{plano.pk}/")
    url = pg.url
    pg.get_by_role("button", name="Cadastrar conjunto", exact=True).click()
    janela = pg.get_by_role("dialog", name="Cadastrar conjunto", exact=True)
    expect(janela).to_be_visible()
    assert janela.locator(".atividade__meta").count() == 0
    marcadas = janela.locator("input[name=atividades]:checked").evaluate_all(
        "els => els.map(e => Number(e.value))")
    assert set(marcadas) == atividades
    janela.get_by_label("Nome do conjunto").fill("CONJUNTO DO REFINO SINTÉTICO")
    with pg.expect_response(lambda r: r.request.method == "POST"
                            and "/conjuntos/" in r.url) as cadastro:
        janela.get_by_role("button", name="Cadastrar conjunto", exact=True).click()
    assert cadastro.value.ok
    assert "application/json" in cadastro.value.headers["content-type"]
    expect(janela).not_to_be_visible()
    expect(pg).to_have_url(url)
    expect(pg.locator("#aplicar-conjunto option").filter(
        has_text="CONJUNTO DO REFINO SINTÉTICO")).to_have_count(1)
    plano.refresh_from_db()
    assert set(plano.atividades.values_list("pk", flat=True)) == atividades
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 1440])
def test_refino_etapas_atividades_e_coordenacao(logado, dados_e2e, largura):
    pg = logado
    plano = _completo(dados_e2e)
    pg.set_viewport_size({"width": largura, "height": 900})
    pg.goto(f"/viagens/planos/{plano.pk}/")
    expect(pg.locator("[data-indice-preparacao]")).to_have_count(0)
    pg.locator("#efetivo").scroll_into_view_if_needed()
    expect(pg.locator("#efetivo #efetivo-linhas")).to_be_visible()
    expect(pg.locator("#efetivo #diarias")).to_have_count(1)
    assert pg.locator("#eventos").evaluate("e => !e.closest('#documento')")
    expect(pg.locator("#eventos")).to_contain_text("apenas o evento principal")
    grupos = pg.locator(".plano-coordenacoes > .coordenador")
    expect(grupos).to_have_count(2)
    if largura == 1440:
        a, b = grupos.all()
        assert abs(a.bounding_box()["y"] - b.bounding_box()["y"]) < 1
    atividades = pg.locator("#atividades .atividade")
    assert atividades.evaluate_all("""els => els.every(e => {
        const nome = e.querySelector('.atividade__nome');
        return nome.scrollWidth <= nome.clientWidth + 1;
    })""")
    expect(atividades.locator(".atividade__meta")).to_have_count(0)
    pg.get_by_role("searchbox", name="Buscar atividade", exact=True).fill("inexistente-refino")
    expect(pg.locator("#atividades .atividade:visible")).to_have_count(0)
    expect(pg.locator("#atividades [data-sem-resultado]")).to_be_visible()
    pg.get_by_role("searchbox", name="Buscar atividade", exact=True).fill("")
    expect(pg.locator("#atividades .atividade:visible")).to_have_count(atividades.count())
    pg.get_by_role("button", name="Adicionar efetivo", exact=True).click()
    linhas = pg.locator("#efetivo-linhas [data-linha]")
    expect(linhas).to_have_count(2)
    expect(linhas.last.locator(".campo__rotulo").first).to_be_visible()
    linhas.last.get_by_role("button", name="Remover a linha do efetivo 2").click()
    expect(linhas).to_have_count(1)
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pg.goto("/viagens/planos/")
    expect(pg.locator(".registro__meta-item--coordenacao")).to_contain_text(
        plano.coordenador_adm.nome)
    assert pg.erros_console == []


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_preparacao_quantidade_calendario_e_conferencia(logado, dados_e2e, largura):
    pg = logado
    plano = _completo(dados_e2e)
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto(f"/viagens/planos/{plano.pk}/")
    expect(pg.get_by_role("heading", level=1)).to_contain_text(str(plano))
    expect(pg.locator(".registro-hero .identidade-documental__complemento")).to_have_text(
        plano.sufixo)
    expect(pg.locator("#conferencia")).to_contain_text("dá para gerar o plano")
    escolhas_coordenacao = pg.locator('.campos--coordenacao pc-select .seletor__valor:visible')
    expect(escolhas_coordenacao.first).to_be_visible()
    assert escolhas_coordenacao.evaluate_all(
        "els => els.every(e => e.scrollWidth <= e.clientWidth)"
    ), "A origem e o tratamento da coordenação devem ser legíveis sem truncamento"
    assert pg.get_by_role("button", name="Programa", exact=True).bounding_box()["width"] > 200
    quantidade = pg.locator("#efetivo-quantidade-1")
    # Área de toque válida e três dígitos (limite 999) legíveis, sem limiar arbitrário.
    assert quantidade.bounding_box()["width"] >= 24
    assert quantidade.evaluate("""e => {
        const s = getComputedStyle(e), c = document.createElement('canvas').getContext('2d');
        c.font = s.font;
        return c.measureText('999').width <= e.clientWidth - parseFloat(s.paddingLeft)
            - parseFloat(s.paddingRight);
    }""")
    quantidade.fill("3")
    pg.locator("#efetivo-linhas").get_by_role("button", name="Aumentar a quantidade").click()
    expect(quantidade).to_have_value("4")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    plano.refresh_from_db()
    assert plano.efetivo.get().quantidade == 4
    calendario = pg.locator("pc-data[data-periodo] .seletor__botao")
    calendario.focus()
    calendario.press("Enter")
    expect(calendario).to_have_attribute("aria-expanded", "true")
    pg.keyboard.press("Escape")
    expect(calendario).to_be_focused()
    expect(pg.locator("#diarias .conferencia-serena--operacional")).to_contain_text("R$")
    assert pg.locator(".barra-acoes").evaluate("e => getComputedStyle(e).position") == "sticky"  # rodapé grudado, como no ofício
    pg.evaluate("scrollTo(0,0)")
    assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth")
    pasta = Path("artifacts/planos-preparacao-identidade")
    pasta.mkdir(parents=True, exist_ok=True)
    violacoes = rodar_axe(pg)
    if violacoes:
        geometria = pg.evaluate("""violacoes => ({scrollY, alvos: violacoes.flatMap(v =>
            v.nodes.map(n => {const e = document.querySelector(n.target[0]);
                return {target: n.target, rect: e?.getBoundingClientRect().toJSON(),
                    html: e?.outerHTML};}))})""", violacoes)
        (pasta / f"axe-{largura}.json").write_text(
            json.dumps({"violacoes": violacoes, "geometria": geometria}, ensure_ascii=False,
                       indent=2), encoding="utf-8")
        pg.screenshot(path=str(pasta / f"axe-{largura}.png"))
    assert violacoes == []
    pg.screenshot(path=str(pasta / f"preparacao-{largura}.png"), full_page=True)
    assert pg.erros_console == []


def test_evento_manual_diarias_menu_remocao_e_pdf(logado, dados_e2e):
    pg = logado
    plano = _completo(dados_e2e)
    valor_principal = plano.diarias_total
    pg.goto(f"/viagens/planos/{plano.pk}/")
    pg.get_by_role("link", name="Acrescentar evento").click()
    janela = pg.get_by_role("dialog", name="Novo evento", exact=True)
    expect(janela).to_be_visible()
    assert janela.locator("form").evaluate("e => !e.closest('#form-plano')")
    janela.get_by_role("button", name="Programa", exact=True).click()
    janela.get_by_role("checkbox", name="Outro", exact=True).check()
    janela.get_by_role("button", name="Programa", exact=True).click()
    janela.get_by_label("Outro programa", exact=True).fill("Feira institucional sintética")
    janela.locator("pc-data[data-periodo] .mesa-evento__botao").click()
    foco = date.fromisoformat(janela.locator(".calendario td[tabindex='0']").get_attribute("data-data"))
    meses = (2030 - foco.year) * 12 + 6 - foco.month
    for _ in range(abs(meses)):
        pg.keyboard.press("PageDown" if meses > 0 else "PageUp")
    dia = janela.locator(".calendario td[data-data='2030-06-28']")
    dia.click()
    dia.click()
    janela.get_by_role("combobox", name="Destino 1", exact=True).fill("Maringá")
    janela.get_by_role("option", name="Maringá/PR", exact=True).click()
    cargo = janela.get_by_role("combobox", name="Cargo", exact=True)
    cargo.fill("Agente de Polícia")
    janela.get_by_role("option", name="Agente de Polícia Judiciária", exact=True).click()
    janela.locator("#evento-efetivo-quantidade-1").fill("2")
    for campo, valor in {"evento_saida_em_0": "28/06/2030", "evento_saida_em_1": "06:00",
                         "evento_chegada_em_0": "28/06/2030", "evento_chegada_em_1": "21:00"}.items():
        janela.locator(f"#{campo}").fill(valor)
    janela.get_by_role("button", name="Acrescentar evento", exact=True).click()
    expect(pg.locator("#eventos .registro-operacional")).to_have_count(1)
    plano.refresh_from_db()
    evento = plano.eventos.get()
    assert evento.diarias_total is not None
    registro = pg.locator("#eventos .registro__link")
    expect(registro).to_have_attribute("title", "Maringá/PR")
    expect(registro).to_have_accessible_name("Editar o evento 2 · Maringá/PR")
    registro.click()
    edicao = pg.get_by_role("dialog", name="Editar evento", exact=True)
    expect(edicao).to_be_visible()
    edicao.get_by_label("Outro programa", exact=True).fill("")
    with pg.expect_response(lambda r: r.request.method == "POST"
                            and r.url.endswith("/eventos/salvar/")) as invalido:
        edicao.get_by_role("button", name="Salvar evento", exact=True).click()
    assert invalido.value.status == 422
    expect(pg.get_by_role("dialog", name="Editar evento", exact=True)).to_be_visible()
    expect(pg.get_by_role("dialog", name="Editar evento", exact=True).locator(".campo__erro").first).to_be_visible()
    evento.refresh_from_db()
    assert str(evento.data_inicio) == "2030-06-28"
    pg.get_by_role("dialog", name="Editar evento", exact=True).get_by_role("link", name="Cancelar", exact=True).click()
    assert plano.diarias_total == valor_principal
    assert planos.diarias_geral(plano) == valor_principal + evento.diarias_total
    assert planos.efetivo_geral(plano) == 8
    pg.locator("#eventos").get_by_role("button", name="Ações do evento 2").press("Enter")
    expect(pg.get_by_role("menuitem", name="Editar evento", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(pg.get_by_role("button", name="Ações do evento 2")).to_be_focused()
    with pg.expect_response(lambda r: r.request.method == "POST"
                            and r.url.endswith("/finalizar/")) as finalizacao:
        pg.locator("#conferencia").get_by_role("button", name="Finalizar e gerar o plano").click()
    assert finalizacao.value.status == 302
    plano.refresh_from_db()
    assert plano.gerado
    resposta = pg.request.get(f"/viagens/planos/{plano.pk}/documento.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    pg.goto(f"/viagens/planos/{plano.pk}/")
    pg.get_by_role("button", name="Ações do evento 2").click()
    pg.get_by_role("menuitem", name="Remover evento", exact=True).click()
    pg.get_by_role("dialog", name="Remover evento?", exact=True).get_by_role(
        "button", name="Remover evento", exact=True).click()
    expect(pg.locator("#eventos .registro-operacional")).to_have_count(0)
    assert not plano.eventos.exists()
    pg.goto("/viagens/planos/")
    pg.wait_for_load_state("networkidle")
    # HTTP 422 é deliberado neste cenário; nenhuma falha de JS ou outro recurso.
    assert pg.erros_console == [
        "Failed to load resource: the server responded with a status of 422 (Unprocessable Content)",
    ]
