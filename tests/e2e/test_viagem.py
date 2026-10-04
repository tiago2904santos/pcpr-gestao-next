"""E2E: nova viagem → tipo e destino gravam sozinhos (o título nasce do tipo) → vincular o
ofício → criar a OS já vinculada pela viagem."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_viagem_do_zero(logado, dados_e2e):
    from gestao.cadastros.models import TipoViagem
    from gestao.viagens.models import OrdemServico, Viagem

    TipoViagem.objects.create(nome="Unidade Móvel")
    pg = logado
    pg.goto("/viagens/viagens/")
    pg.get_by_role("button", name="Nova viagem").first.click()
    expect(pg.get_by_text("Falta o tipo")).to_be_visible()
    pg.get_by_role("checkbox", name="Unidade Móvel", exact=True).check()
    # O título nasce do tipo: gravou e a tela se refez com ele.
    expect(pg.locator("#frase-viagem")).to_contain_text("Unidade Móvel")
    v = Viagem.objects.get()
    assert v.titulo == "Unidade Móvel"

    # Vincular o ofício emitido (a lista abre ao clicar).
    pg.locator("#vinculos summary", has_text="Ofícios").click()
    pg.locator("#vinculos").get_by_role("checkbox").first.check()
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(pg.locator("#documentos")).not_to_contain_text("Nenhum ofício vinculado")

    # Nova OS já vinculada.
    pg.locator("button[form=novo-ordem]").click()
    expect(pg.locator(".toast")).to_contain_text("criado já vinculado à viagem")
    assert OrdemServico.objects.get(viagem=v)
