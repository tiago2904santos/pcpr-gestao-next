"""E2E: Coffee Break CB1 — o administrador do módulo cadastra fornecedor, contrato e lote
pela janela, edita a configuração do ofício; as telas sem rolagem horizontal."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _admin_do_modulo() -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    u = Usuario.objects.get(login="operador")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"),
                 Group.objects.get(name="ADMINISTRADOR"))


def test_cadastrar_fornecedor_contrato_e_lote(logado, dados_e2e):
    from gestao.cadastros.models import Municipio
    from gestao.coffee.models import Contrato, Fornecedor, Lote

    _admin_do_modulo()
    Municipio.objects.get_or_create(codigo_ibge="4106902",
                                    defaults={"nome": "Curitiba", "uf": "PR"})
    pg = logado
    pg.goto("/coffee/cadastros/fornecedores/")
    pg.get_by_role("button", name="Novo fornecedor").first.click()
    pg.locator("#id_razao_social").fill("Buffet de Teste Ltda (e2e)")
    pg.locator("#id_cnpj").fill("11.222.333/0001-81")
    pg.locator("#dialogo-cadastro").get_by_role("button", name="Salvar", exact=True).click()
    expect(pg.locator(".registros")).to_contain_text("Buffet de Teste Ltda (e2e)")
    f = Fornecedor.objects.get()
    assert f.cnpj == "11222333000181"

    pg.goto("/coffee/cadastros/contratos/?novo=1")
    pg.get_by_role("combobox", name="Fornecedor").click()
    pg.get_by_role("option", name="Buffet de Teste Ltda (e2e)").click()
    pg.locator("#id_numero").fill("9/2026")
    pg.locator("#id_valor_unitario").fill("21,07")
    pg.locator("#dialogo-cadastro").get_by_role("button", name="Salvar", exact=True).click()
    expect(pg.locator(".registros")).to_contain_text("Contrato 9/2026")
    assert str(Contrato.objects.get().valor_unitario) == "21.0700"

    pg.goto("/coffee/cadastros/lotes/?novo=1")
    pg.get_by_role("combobox", name="Contrato").click()
    pg.get_by_role("option", name="Contrato 9/2026").click()
    pg.locator("#id_numero").fill("1")
    pg.locator("#id_exercicio").fill("2026")
    pg.locator("#id_quantidade_total").fill("1000")
    pg.locator("#id_lista_municipios").fill("Curitiba")
    pg.locator("#dialogo-cadastro").get_by_role("button", name="Salvar", exact=True).click()
    expect(pg.locator(".registros")).to_contain_text("Lote 1 (2026)")
    assert [m.nome for m in Lote.objects.get().municipios.all()] == ["Curitiba"]

    pg.goto("/coffee/cadastros/oficio/")
    pg.locator("#id_assinante").fill("Chefe da ASCOM (e2e)")
    pg.get_by_role("button", name="Salvar configuração").click()
    expect(pg.get_by_role("status").first).to_be_attached()
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_sem_rolagem_horizontal(logado, dados_e2e, largura):
    _admin_do_modulo()
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/coffee/cadastros/fornecedores/", "/coffee/cadastros/contratos/?novo=1",
                 "/coffee/cadastros/aditivos/", "/coffee/cadastros/lotes/?novo=1",
                 "/coffee/cadastros/oficio/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
