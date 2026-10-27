"""E2E: diário de bordo (módulo 9b) — da lista da prestação para o diário; os km gravam
sozinhos; a conferência avisa o hodômetro que volta para trás; trocar a viatura só no
diário (os campos do modo aparecem ao marcar)."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_diario_do_km_a_troca_de_viatura(logado, dados_e2e):
    from gestao.viagens.models import DiarioBordo, PrestacaoContas

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.goto("/viagens/prestacoes/")
    pg.locator(f"#equipe-{p.pk}").get_by_role("button", name="Ações da prestação do").click()
    pg.get_by_role("menuitem", name="1 · Diário de bordo").click()
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Diário de bordo")
    d = DiarioBordo.objects.get(prestacao=p)
    a, b = d.linhas.order_by("ordem")
    pg.locator(f"#l-{a.pk}-km_inicial").fill("10000")
    pg.locator(f"#l-{a.pk}-km_final").fill("10400")
    pg.locator(f"#l-{b.pk}-km_inicial").fill("10300")
    pg.locator(f"#l-{b.pk}-km_final").fill("10700")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    expect(pg.locator("#conferencia")).to_contain_text("o hodômetro voltou para trás")
    a.refresh_from_db()
    assert (a.km_inicial, a.km_final) == (10000, 10400)

    # Outra viatura do cadastro: o campo aparece só ao marcar, e grava sozinho. ("Informar à
    # mão" saiu da tela; viatura nova se cadastra pelo "+".)
    expect(pg.locator("#motorista form")).to_be_visible()
    cadastro = pg.get_by_role("combobox", name="Viatura do cadastro")
    expect(cadastro).to_be_hidden()
    pg.get_by_role("combobox", name="Viatura", exact=True).click()
    expect(pg.get_by_role("option", name="Informar à mão")).to_have_count(0)
    pg.get_by_role("option", name="Outra do cadastro").click()
    cadastro.fill("Duster")
    pg.get_by_role("option", name="Duster").first.click()
    expect(pg.locator("#viatura-atual")).to_contain_text("Duster")
    expect(pg.locator("#estado-recursos")).to_contain_text("Trocados só neste diário")
    d.refresh_from_db()
    assert d.viatura_modo == "cadastro"
    assert d.viatura.modelo == "Renault Duster"


def test_viagem_realizada_ajusta_e_recalcula(logado, dados_e2e):
    from gestao.viagens.models import PrestacaoContas

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/diario/")
    pg.get_by_role("button", name="Ajustar horários").click()
    expect(pg.locator("#realizada")).to_contain_text("Ajustados")
    volta = p.trechos_realizados.order_by("-ordem").first()
    pg.locator(f"#r-{volta.pk}-chegada_hora").fill("23:30")
    pg.get_by_role("button", name="Salvar horários e recalcular").click()
    expect(pg.locator(".toast").first).to_contain_text("diárias foram recalculadas")
    expect(pg.locator("#realizada")).to_contain_text("Em relação ao ofício")
