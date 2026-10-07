"""E2E: plano de trabalho a partir do ofício — efetivo em linhas, conjunto de atividades,
gravação automática com a tela acompanhando, finalizar e gerar o documento."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import PlanoTrabalho

pytestmark = pytest.mark.e2e


def test_plano_a_partir_do_oficio(logado, dados_e2e):
    from gestao.cadastros.models import AtividadePlano, PresetAtividades

    conjunto = PresetAtividades.objects.create(nome="BÁSICO", padrao=False)
    conjunto.atividades.set(AtividadePlano.objects.filter(codigo__in=["CIN", "BO"]))
    pg = logado
    pg.goto(f"/viagens/oficios/?resumo={dados_e2e.ids['oficio_emitido']}")
    janela = pg.get_by_role("dialog")
    janela.get_by_role("button", name="Mais ações").click()
    janela.get_by_role("menuitem", name="Criar a partir deste ofício").press("Enter")
    janela.get_by_role("menuitem", name="Novo plano de trabalho").press("Enter")
    pg.get_by_role("dialog", name="Novo plano de trabalho?").get_by_role(
        "button", name="Criar plano").click()
    expect(pg.locator(".toast")).to_contain_text("criado a partir do Ofício")
    plano = PlanoTrabalho.objects.get()
    expect(pg.get_by_role("heading", level=1)).to_contain_text(str(plano))
    # Do ofício: destino, efetivo (2 linhas) e as diárias já calculadas.
    expect(pg.locator(".linhas__linha")).to_have_count(2)
    expect(pg.locator("#diarias")).to_contain_text("R$")

    # Programa do catálogo: grava sozinho e a frase do topo acompanha.
    pg.get_by_role("combobox", name="Programa").click()
    pg.get_by_role("option", name="PROGRAMA PARANÁ EM AÇÃO").click()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(pg.locator("#frase-plano")).to_contain_text("PROGRAMA PARANÁ EM AÇÃO")

    # Mais uma linha no efetivo (componente pc-linhas): a nova recebe o foco.
    pg.get_by_role("button", name="Adicionar linha").click()
    expect(pg.locator(".linhas__linha")).to_have_count(3)
    expect(pg.locator(".linhas__linha").last.get_by_role("combobox").first).to_be_focused()

    # Aplicar o conjunto marca as atividades dele (substitui a seleção, que estava vazia).
    pg.get_by_role("combobox", name="Aplicar conjunto").click()
    pg.get_by_role("option", name=re.compile("BÁSICO")).click()
    expect(pg.get_by_role("checkbox", name=re.compile("Carteira de Identidade"))).to_be_checked()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(pg.locator("#metas-recursos")).to_contain_text("Ampliar o acesso")
    plano.refresh_from_db()
    assert set(plano.atividades.values_list("codigo", flat=True)) == {"CIN", "BO"}

    # Coordenador administrativo por busca; depois, nada falta: finalizar.
    busca = pg.get_by_label("Coordenador administrativo")
    busca.fill("ana")
    pg.get_by_role("option").first.click()
    pg.locator("#identificacao").get_by_role("combobox", name="Como sai no documento").first.click()
    pg.get_by_role("option", name="a Coordenadora").click()
    expect(pg.locator("#conferencia")).to_contain_text("dá para gerar o plano")
    pg.locator("#conferencia").get_by_role("button", name="Finalizar e gerar o plano").click()
    expect(pg.locator(".toast")).to_contain_text("gerado")
    plano.refresh_from_db()
    assert plano.gerado and plano.documento_gerado_em
    assert "Coordenadora Administrativa" in plano.coordenacao
    resposta = pg.request.get(f"/viagens/planos/{plano.pk}/documento.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    assert pg.erros_console == []  # type: ignore[attr-defined]
