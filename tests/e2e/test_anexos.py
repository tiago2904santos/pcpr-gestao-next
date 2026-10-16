"""E2E: anexos da prestação (módulo 9d) na leitura e conferência — os arquivos chegam pelo
importador; aqui se confere, remove e traz de volta."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_leitura_remover_e_trazer_de_volta(logado, dados_e2e):
    from gestao.identidade.models import Usuario
    from gestao.viagens import anexos
    from gestao.viagens.models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    operador = Usuario.objects.get(login="operador")
    anexos.anexar(operador, p.pk, "despacho", nome="despacho.pdf",
                  conteudo=b"%PDF-1.4 teste e2e")
    anexos.anexar(operador, p.pk, "comprovante", servidor_pk=a.pk, nome="saque.pdf",
                  conteudo=b"%PDF-1.4 saque")
    pg = logado
    pg.goto("/viagens/prestacoes/")
    pg.locator(f"#equipe-{p.pk}").get_by_role("button", name="Ações da prestação do").click()
    expect(pg.get_by_role("menuitem", name="3 · Documentos")).to_have_count(0)
    pg.get_by_role("menuitem", name="3 · Leitura e conferência").click()
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Leitura e conferência")
    expect(pg.locator("#despacho")).to_contain_text("despacho.pdf")
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("saque.pdf")

    pg.locator("#comprovantes").get_by_role("button", name="Remover saque.pdf").click()
    confirmar = pg.get_by_role("dialog", name="Remover saque.pdf?")
    expect(confirmar).to_be_visible()
    confirmar.get_by_role("button", name="Remover", exact=True).click()
    expect(pg.locator("#anteriores")).to_contain_text("saque.pdf")
    expect(pg.locator(f"#ps-{a.pk}")).not_to_contain_text("saque.pdf")
    pg.locator("#anteriores").get_by_role("button", name="Trazer de volta saque.pdf").click()
    expect(pg.locator("#comprovantes")).to_contain_text("saque.pdf")
    assert AnexoPrestacao.objects.filter(tipo="comprovante", removido_em__isnull=True).count() == 1
