"""E2E: prestação de contas (módulo 9a) — o ofício emitido já tem a prestação; na lista, o
nº da solicitação e o prazo de saque de cada servidor gravam sozinhos; Enter grava a linha
(não aciona ação nenhuma); finalizar com pendência pede justificativa na própria linha;
registrar envio."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_prestacao_da_linha_ao_envio(logado, dados_e2e):
    from gestao.identidade.models import Usuario
    from gestao.viagens import diario
    from gestao.viagens.models import PrestacaoServidor

    a, b = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=dados_e2e.ids["oficio_emitido"]).order_by("servidor__nome")
    # O diário de bordo da equipe preenchido (a finalização também cobra).
    d = diario.obter(a.prestacao)
    diario.salvar_linhas(Usuario.objects.get(login="operador"), d.pk, {
        linha.pk: {"km_inicial": 10000 + i * 400, "km_final": 10300 + i * 400}
        for i, linha in enumerate(diario.linhas(d))})
    from gestao.viagens import relatorio
    rt = relatorio.obter(a.prestacao)
    relatorio.salvar(Usuario.objects.get(login="operador"), rt.pk, {
        "motivo": "Evento (teste).", "atividade": "Apoio (teste).", "conclusao": "Feito."})
    from gestao.viagens import anexos
    operador = Usuario.objects.get(login="operador")
    anexos.anexar(operador, a.prestacao_id, "despacho", nome="d.pdf", conteudo=b"%PDF-1.4 t")
    # Só o primeiro tem comprovante: o segundo fica com pendência (finalizar pede justificativa).
    anexos.anexar(operador, a.prestacao_id, "comprovante", servidor_pk=a.pk,
                  nome="c.pdf", conteudo=b"%PDF-1.4 t")
    pg = logado
    pg.goto("/viagens/prestacoes/")
    linha = pg.locator(f"#ps-{a.pk}")
    expect(linha).to_contain_text(a.servidor.nome)
    linha.locator(f"#ps-{a.pk}-numero").fill("2030/0007")
    linha.locator(f"#ps-{a.pk}-saque").fill("06/01/2030 a 09/01/2030")
    linha.locator(f"#ps-{a.pk}-saque").press("Tab")  # o período digitado vale ao sair do campo
    expect(linha.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    a.refresh_from_db()
    assert a.numero_solicitacao == "2030/0007"
    assert (str(a.data_liberacao_diarias), str(a.prazo_limite_saque)) == ("2030-01-06", "2030-01-09")
    # As pendências da linha se refazem depois da gravação: some o "para finalizar".
    expect(linha).not_to_contain_text("para finalizar")

    # Enter num campo grava a linha — não finaliza ninguém.
    outro = pg.locator(f"#ps-{b.pk}")
    outro.locator(f"#ps-{b.pk}-numero").fill("2030/0008")
    outro.locator(f"#ps-{b.pk}-numero").press("Enter")
    expect(pg.locator(".toast").first).to_contain_text(f"Solicitação de {b.servidor.nome} salva")
    b.refresh_from_db()
    assert b.numero_solicitacao == "2030/0008" and not b.finalizada
    a.refresh_from_db()
    assert not a.finalizada

    # Sem pendência: finaliza direto.
    pg.locator(f"#ps-{a.pk}").get_by_role("button", name="Finalizar", exact=True).click()
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("Finalizada")

    # Com pendência (sem comprovante): explica e oferece finalizar com justificativa.
    outro = pg.locator(f"#ps-{b.pk}")
    outro.get_by_role("button", name="Finalizar", exact=True).click()
    expect(pg.locator(".toast").first).to_contain_text("pendências")
    outro = pg.locator(f"#ps-{b.pk}")
    outro.locator("summary").click()
    outro.get_by_label("Finalizar mesmo assim — justificativa (fica registrada)").fill("Servidor não chegou a viajar.")
    outro.get_by_role("button", name="Finalizar com justificativa").click()
    expect(pg.locator(f"#ps-{b.pk}")).to_contain_text("Justificativa")
    expect(pg.locator(f"#equipe-{a.prestacao_id}").get_by_text("Equipe finalizada")).to_be_visible()

    # Envio ao financeiro (só registra).
    pg.locator(f"#ps-{a.pk}").get_by_role("button", name="Registrar envio").click()
    envio = pg.locator(f"#envio-{a.pk}")
    envio.get_by_role("textbox", name="Protocolo do envio").fill("E-2030-1")
    envio.get_by_role("button", name="Registrar envio").click()
    expect(pg.locator(f"#ps-{a.pk}")).to_contain_text("Enviada")
    a.refresh_from_db()
    assert a.situacao == "enviada" and a.protocolo_envio == "E-2030-1"
    pg.wait_for_load_state("networkidle")
