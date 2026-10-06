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


def _lote_de_curitiba():
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from gestao.cadastros.models import Municipio
    from gestao.coffee.models import Contrato, Fornecedor, Lote

    hoje = timezone.localdate()
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    f = Fornecedor.objects.create(razao_social="Buffet do Lote (e2e)", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="5/2026", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500)
    lote.municipios.set([curitiba])
    return lote


def _operador_do_modulo() -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    Usuario.objects.get(login="operador").groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))


def test_pedir_coffee_break_e_cancelar(logado, dados_e2e):
    from datetime import timedelta

    from django.utils import timezone

    from gestao.coffee.models import Solicitacao

    _operador_do_modulo()
    _lote_de_curitiba()
    data = timezone.localdate() + timedelta(days=15)
    pg = logado
    pg.goto("/coffee/nova/")
    pg.locator("#id_municipio").fill("Curitiba/PR")
    pg.locator("#id_municipio").press("Tab")
    expect(pg.locator("#lote-do-municipio")).to_contain_text("Lote 1")
    expect(pg.locator("#lote-do-municipio")).to_contain_text("500 de 500 unidades")
    pg.locator("#id_descricao").fill("Posse da diretoria (e2e)")
    pg.locator("#id_quantidade").fill("40")
    pg.locator("#id_data_evento").fill(f"{data:%d/%m/%Y}")
    pg.get_by_role("button", name="Registrar solicitação").click()
    expect(pg.locator(".registros")).to_contain_text("Posse da diretoria (e2e)")
    s = Solicitacao.objects.get()
    assert s.quantidade == 40 and s.lote.numero == 1

    pg.goto(f"/coffee/solicitacoes/{s.pk}/")
    expect(pg.locator("#lote-do-municipio")).to_contain_text("460 de 500 unidades")
    pg.get_by_role("button", name="Cancelar", exact=True).click()
    pg.locator("#dialogo-motivo-texto").fill("Evento adiado (e2e)")
    pg.locator("#dialogo-motivo").get_by_role("button", name="Cancelar solicitação").click()
    expect(pg.locator(".alerta--perigo")).to_contain_text("Solicitação cancelada")
    s.refresh_from_db()
    assert s.cancelada and s.motivo_cancelamento == "Evento adiado (e2e)"
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_solicitacoes_sem_rolagem_horizontal(logado, dados_e2e, largura):
    from gestao.coffee import pedidos
    from gestao.identidade.models import Usuario

    _operador_do_modulo()
    lote = _lote_de_curitiba()
    from django.utils import timezone
    s = pedidos.salvar(Usuario.objects.get(login="operador"), {
        "municipio": lote.municipios.get(), "data_solicitacao": timezone.localdate(),
        "numero": "", "descricao": "Evento com uma descrição bem comprida para testar a quebra "
        "de linha no cabeçalho da folha (e2e)", "quantidade": 30}).solicitacao
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/coffee/", "/coffee/nova/", f"/coffee/solicitacoes/{s.pk}/", "/coffee/lotes/",
                 "/coffee/certidoes/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"


def test_andamento_do_proximo_marco(logado, dados_e2e):
    """CB3a: registrar a nota pelo andamento e ver a etapa seguinte como a atual."""
    from django.utils import timezone

    from gestao.coffee import pedidos
    from gestao.identidade.models import Usuario

    _operador_do_modulo()
    lote = _lote_de_curitiba()
    s = pedidos.salvar(Usuario.objects.get(login="operador"), {
        "municipio": lote.municipios.get(), "data_solicitacao": timezone.localdate(),
        "numero": "", "descricao": "Evento do andamento (e2e)", "quantidade": 30}).solicitacao
    pg = logado
    pg.goto(f"/coffee/solicitacoes/{s.pk}/#situacao")
    pg.locator("#andamento-valor").fill("8957")
    pg.locator("#andamento-anotacao").fill("Nota por e-mail (e2e)")
    pg.get_by_role("button", name="Registrar andamento").click()
    expect(pg.locator(".etapas-progresso__item--atual")).to_contain_text("Protocolo")
    expect(pg.locator("#historico")).to_contain_text("Número da nota fiscal: 8957")
    s.refresh_from_db()
    assert s.nota_fiscal == "8957" and s.situacao == "aguardando_protocolo"
    assert not pg.erros_console  # type: ignore[attr-defined]
