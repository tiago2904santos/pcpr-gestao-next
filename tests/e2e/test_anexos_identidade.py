"""Documentos da prestação: correção operável em cada largura."""

import re

import pytest
from playwright.sync_api import expect

from gestao.identidade.models import Usuario
from gestao.viagens import anexos
from gestao.viagens.models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_correcao_comprovante_preserva_arquivo_e_foco(logado, dados_e2e, largura):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    ps = PrestacaoServidor.objects.filter(prestacao=p).first()
    anexos.anexar(Usuario.objects.get(login="operador"), p.pk, "comprovante",
                  servidor_pk=ps.pk, nome="comprovante-transferencia-equipe.pdf",
                  conteudo=b"%PDF-1.4 teste isolado")
    a = AnexoPrestacao.objects.get(servidor=ps)
    arquivo = a.arquivo.name
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/documentos/")
    expect(pg.get_by_role("heading", level=1)).to_contain_text(ps.servidor.nome)
    expect(pg.get_by_role("heading", name="Documentos e fechamento")).to_be_visible()
    cartao = pg.locator(f"#ps-{ps.pk}")
    corrigir = cartao.get_by_role("button", name=re.compile("^Corrigir valor"))
    corrigir.focus()
    pg.keyboard.press("Enter")
    campo = cartao.locator(f"#a{a.pk}-valor")
    expect(campo).to_be_visible()
    campo.fill("R$ 15,00")
    cartao.locator(f"#a{a.pk}-data").fill("10/10/2026")
    form = campo.locator("xpath=ancestor::form")
    operacao = form.get_by_role("combobox", name="Operação")
    operacao.click()
    pg.get_by_role("option", name="Pix", exact=True).click()
    expect(operacao).to_be_focused()
    form.get_by_role("button", name="Salvar", exact=True).click()
    expect(pg.locator(".toast").first).to_contain_text("Comprovante atualizado")
    a.refresh_from_db()
    assert str(a.valor) == "15.00"
    assert a.operacao == "pix"
    assert a.data_operacao.isoformat() == "2026-10-10"
    assert a.arquivo.name == arquivo
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert pg.erros_console == []


def test_carimbo_responsivo_preserva_via_assinada(logado, dados_e2e):
    import hashlib
    import os
    from pathlib import Path

    from gestao.plataforma import outbox
    from gestao.viagens import assinados, prestacao
    from gestao.viagens.models import CarimboSolicitacao, ViaAssinada

    while outbox.processar_lote():
        pass
    operador = Usuario.objects.get(login="operador")
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    alvo = assinados.Alvo(ViaAssinada.Tipo.OFICIO, p.oficio)
    with assinados.documento_emitido(p.oficio, "oficio").arquivo.open("rb") as f:
        assinados.anexar(operador, alvo, nome="oficio-assinado.pdf", conteudo=f.read())
    via = assinados.vigente(alvo)
    with via.arquivo.open("rb") as f:
        original = hashlib.sha256(f.read()).hexdigest()
    ps = prestacao.ativos().filter(prestacao=p).first()
    prestacao.salvar_solicitacao(operador, ps.pk, numero="2030/1", liberacao=None, prazo=None)
    pg = logado
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/documentos/")
    pg.get_by_text("Posição do número da solicitação no ofício assinado", exact=True).click()
    for largura in [360, 768, 1440]:
        pg.set_viewport_size({"width": largura, "height": 900})
        expect(pg.locator(f"#c{ps.pk}-x")).to_be_visible()
        assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
        if os.environ.get("MIGRACAO_CAPTURAS"):
            destino = Path(os.environ["MIGRACAO_CAPTURAS"])
            destino.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=str(destino / f"anexos-carimbo-isolado-{largura}.png"),
                          full_page=True, animations="disabled")
    pg.locator(f"#c{ps.pk}-x").fill("20")
    pg.locator(f"#c{ps.pk}-y").fill("30")
    pg.get_by_role("button", name=f"Salvar posição do número de {ps.servidor.nome}").click()
    expect(pg.locator(".toast").first).to_contain_text("Posição do número salva")
    posicao = CarimboSolicitacao.objects.get(servidor=ps)
    assert float(posicao.x) == pytest.approx(0.2)
    assert float(posicao.y) == pytest.approx(0.3)
    with via.arquivo.open("rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == original
