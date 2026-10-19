"""E2E da automação (WhatsApp simulado): ligar as chaves, cadastrar o contato com opt-in e o
testador pela tela, registrar a liberação fictícia de diárias, processar a fila pelo
simulador, ver a mensagem enviada, responder com um comprovante fictício e vê-lo associado
— mais axe sem violações graves e sem rolagem horizontal de 360 a 1440 px."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from playwright.sync_api import expect

from .conftest import rodar_axe

pytestmark = pytest.mark.e2e
PDF = b"%PDF-1.4\n% comprovante ficticio e2e\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _preparar(admin: bool = True):
    from django.contrib.auth.models import Group
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.viagens import prestacao
    from gestao.viagens.models import PrestacaoServidor

    op = Usuario.objects.get(login="operador")
    if admin:
        op.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    ps = (PrestacaoServidor.objects.filter(prestacao__oficio__situacao="emitido",
                                           prestacao__oficio__unidade=op.lotacao.unidade)
          .select_related("servidor").order_by("pk").first())
    ps.servidor.telefone = "41999990001"
    ps.servidor.save(update_fields=["telefone"])
    hoje = timezone.localdate()
    return op, ps, lambda: prestacao.salvar_solicitacao(
        op, ps.pk, numero="E2E-1", liberacao=hoje, prazo=hoje + timedelta(days=5))


def _ligar_chave(pg, rotulo: str, modo: str = "") -> None:
    item = pg.locator(".registro", has=pg.get_by_text(rotulo, exact=True))
    item.get_by_role("combobox", name="Estado").click()
    pg.get_by_role("option", name="Ligada", exact=True).click()
    if modo:
        item.get_by_role("combobox", name="Modo").click()
        pg.get_by_role("option", name=modo).click()
    item.get_by_role("button", name=f"Salvar {rotulo}").click()
    expect(pg.locator(".registro", has=pg.get_by_text(rotulo, exact=True))
           ).to_contain_text("Ligada")


def test_fluxo_completo_pelo_navegador(logado, dados_e2e):
    from gestao.automacao.models import Comunicacao, Recebimento
    from gestao.viagens.models import AnexoPrestacao

    _, ps, liberar = _preparar()
    pg = logado
    pg.goto("/automacao/canal/")
    _ligar_chave(pg, "Chave geral")
    _ligar_chave(pg, "Canal WhatsApp")
    for rotulo in ("Fluxo: Aviso de diárias liberadas",
                   "Fluxo: Respostas automáticas (confirmação, ajuda, descadastro)",
                   "Fluxo: Associar arquivos recebidos automaticamente"):
        _ligar_chave(pg, rotulo, "Automático")

    pg.goto("/automacao/testadores/")
    pg.get_by_label("WhatsApp do testador").fill("(41) 99999-0001")
    pg.get_by_label("Quem é").fill("Testador e2e")
    pg.get_by_role("button", name="Incluir").click()
    expect(pg.get_by_text("Testador e2e")).to_be_visible()

    pg.goto("/automacao/contatos/novo/")
    pg.locator("#id_servidor").select_option(label=ps.servidor.nome)
    pg.get_by_role("button", name="Cadastrar contato").click()
    pg.get_by_role("button", name="Confirmei o número com a pessoa").click()
    pg.get_by_label("Confirmo que a pessoa aceitou").check()
    pg.get_by_role("button", name="Registrar opt-in").click()
    expect(pg.locator(".pagina-cabecalho")).to_contain_text("Ativo")

    liberar()
    pg.goto("/automacao/")
    pg.get_by_role("button", name="Processar a fila agora").click()
    aviso = Comunicacao.objects.get(tipo="viagens.diarias_liberadas")
    assert aviso.situacao == "enviada"
    pg.goto(f"/automacao/comunicacoes/{aviso.pk}/")
    expect(pg.locator("main")).to_contain_text("Enviada")
    expect(pg.locator("main")).to_contain_text("dados fictícios")

    pg.get_by_label("Texto da mensagem").fill("Segue o comprovante")
    pg.get_by_label("Arquivo (comprovante fictício)").set_input_files(
        {"name": "comprovante.pdf", "mimeType": "application/pdf", "buffer": PDF})
    pg.get_by_role("button", name="Simular resposta").click()
    pg.goto("/automacao/")
    pg.get_by_role("button", name="Processar a fila agora").click()
    r = Recebimento.objects.get()
    assert r.situacao == "associado", r.motivo
    assert AnexoPrestacao.objects.filter(servidor=ps, tipo="comprovante").exists()
    pg.goto(f"/automacao/recebidos/{r.pk}/")
    expect(pg.locator("main")).to_contain_text("Associado ao registro")
    pg.get_by_role("button", name="Conferi o arquivo").click()
    expect(pg.locator(".registro-hero")).to_contain_text("Conferido")
    assert not pg.erros_console  # type: ignore[attr-defined]


def test_sem_papel_nao_ve_a_automacao(logado, dados_e2e):
    from gestao.identidade.models import Usuario

    Usuario.objects.get(login="operador").groups.clear()
    pg = logado
    resposta = pg.goto("/automacao/")
    assert resposta is not None and resposta.status == 403


ROTAS = ("/automacao/", "/automacao/comunicacoes/", "/automacao/recebidos/",
         "/automacao/excecoes/", "/automacao/contatos/", "/automacao/contatos/novo/",
         "/automacao/testadores/", "/automacao/canal/", "/automacao/credenciais/",
         "/automacao/aprovacoes/", "/automacao/historico/", "/automacao/links/",
         "/automacao/delegar/", "/ajuda/", "/assistencia/")


def _com_dados():
    from gestao.automacao import contatos, entrega
    from gestao.automacao.models import Comunicacao

    op, ps, liberar = _preparar()
    contato = contatos.cadastrar(op, ps.servidor_id)
    contatos.confirmar_numero(op, contato.pk)
    contatos.registrar_optin(op, contato.pk, "formulario")
    contatos.autorizar_testador(op, "5541999990001", "Testador")
    liberar()
    from gestao.automacao import chaves

    for nome in (chaves.GERAL, chaves.nome_canal("whatsapp"),
                 chaves.nome_fluxo("diarias_liberadas")):
        chaves.alterar(op, nome, estado="ligada", modo="automatico")
    entrega.processar_uma()
    return Comunicacao.objects.get(tipo="viagens.diarias_liberadas")


def test_axe_sem_violacoes_graves(logado, dados_e2e):
    aviso = _com_dados()
    pg = logado
    for rota in (*ROTAS, f"/automacao/comunicacoes/{aviso.pk}/"):
        pg.goto(rota)
        graves = [v for v in rodar_axe(pg) if v["impact"] in ("serious", "critical")]
        assert not graves, f"{rota}: {[(v['id'], v['nodes'][0]['target']) for v in graves]}"
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_sem_rolagem_horizontal(logado, dados_e2e, largura):
    aviso = _com_dados()
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in (*ROTAS, f"/automacao/comunicacoes/{aviso.pk}/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
    assert re.search("automacao", pg.url)
