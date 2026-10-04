"""E2E: ordem de serviço a partir do ofício, tipo com funções e documento."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import OrdemServico

pytestmark = pytest.mark.e2e


def test_os_a_partir_do_oficio_com_funcoes(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/?resumo={dados_e2e.ids['oficio_emitido']}")
    janela = pg.get_by_role("dialog")
    janela.get_by_role("button", name="Mais ações").click()
    janela.get_by_role("menuitem", name="Nova ordem de serviço").press("Enter")
    pg.get_by_role("dialog", name="Nova ordem de serviço?").get_by_role(
        "button", name="Criar OS").click()
    expect(pg.locator(".toast")).to_contain_text("criada a partir do Ofício")
    ordem = OrdemServico.objects.get()
    expect(pg.get_by_role("heading", level=1)).to_contain_text(re.compile(r"/PR"))
    # Tipo com funções: salva o tipo e escolhe a função de cada um da equipe.
    pg.get_by_role("combobox", name="Tipo de necessidade").click()
    pg.get_by_role("option", name=re.compile("Cerimonial")).click()
    pg.get_by_role("button", name="Salvar OS").click()
    # Tipo com função e ninguém com função: a tela pede para escolher.
    expect(pg.locator(".toast")).to_contain_text("escolha a função")
    primeiro = ordem.servidores.order_by("nome").first()
    funcao = pg.get_by_role("combobox", name=primeiro.nome)
    funcao.click()
    pg.get_by_role("option", name="Coordenação").click()
    pg.get_by_role("button", name="Salvar OS").click()
    expect(pg.locator(".toast")).to_contain_text("atualizada")
    ordem.refresh_from_db()
    assert ordem.tipo == "cerimonial_antecipado"
    assert ordem.funcoes.get(str(primeiro.pk)) == "coordenacao"
    resposta = pg.request.get(f"/viagens/ordens/{ordem.pk}/documento.pdf")
    assert resposta.ok and resposta.body().startswith(b"%PDF")
    assert pg.erros_console == []  # type: ignore[attr-defined]
