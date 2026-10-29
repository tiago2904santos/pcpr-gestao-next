"""Entrega 1 do piloto WhatsApp (ADR 0046/0047), de ponta a ponta com o adaptador simulado:
liberação fictícia de diárias → comunicação → envio simulado → status → comprovante
devolvido pelo WhatsApp → associação à prestação certa → confirmação → lembretes encerrados.

E as travas: fora da lista de testadores ou sem opt-in = zero chamada ao canal; chave
desligada = nada sai; resultado desconhecido nunca reenvia; webhook duplicado e status fora
de ordem não bagunçam nada; número desconhecido fica em quarentena sem download.

O envio ao canal recusa rodar com transação aberta (é a regra); aqui os testes rodam dentro
da transação do pytest e desligam essa trava — `test_trava_de_transacao` confere que ela existe.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.automacao import (
    chaves,
    comunicacoes,
    contatos,
    entrada,
    entrega,
    recebimentos,
    simulador,
)
from gestao.automacao.models import (
    Comunicacao,
    ContatoVerificado,
    EntradaWebhook,
    ExcecaoAutomacao,
    Recebimento,
    StatusEntrega,
)
from gestao.identidade.models import Usuario
from gestao.integracoes.whatsapp import webhook
from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado
from gestao.viagens import comunicacoes as viagens_whatsapp
from gestao.viagens import prestacao
from gestao.viagens.models import AnexoPrestacao, PrestacaoServidor

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db

TELEFONE = "41999990001"
E164 = "5541999990001"
PDF = b"%PDF-1.4\n% comprovante ficticio de teste\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
S = Comunicacao.Situacao


class Espiao(AdaptadorSimulado):
    """O simulado, contando as idas ao canal."""

    def __init__(self):
        self.envios = []

    def enviar(self, mensagem, simular=""):
        self.envios.append(mensagem)
        return super().enviar(mensagem, simular)


@pytest.fixture(autouse=True)
def _sem_trava_de_transacao(monkeypatch):
    monkeypatch.setattr(entrega, "VERIFICAR_TRANSACAO", False)


def test_trava_de_transacao(monkeypatch):
    from django.db import transaction
    monkeypatch.setattr(entrega, "VERIFICAR_TRANSACAO", True)
    with transaction.atomic(), pytest.raises(RuntimeError, match="transação aberta"):
        entrega.enviar(entrega.Reserva(0, 0, None), porta=Espiao())
    with transaction.atomic(), pytest.raises(RuntimeError, match="transação aberta"):
        recebimentos.baixar(0)


@pytest.fixture
def c():
    cen = cenario_completo()
    admin = Usuario.objects.create_user("admin-auto", "admin-auto@pc.pr.gov.br", "x",
                                        nome="Administração da automação")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    cen.usuarios["admin"] = admin
    ps = (PrestacaoServidor.objects.filter(prestacao__oficio_id=cen.ids["oficio_emitido"])
          .select_related("servidor").order_by("servidor__nome").first())
    ps.servidor.telefone = TELEFONE
    ps.servidor.save(update_fields=["telefone"])
    cen.ps = ps
    return cen


def _ligar(c, *fluxos, modo="automatico"):
    admin = c.usuarios["admin"]
    chaves.alterar(admin, chaves.GERAL, estado="ligada")
    chaves.alterar(admin, chaves.nome_canal("whatsapp"), estado="ligada")
    for fluxo in fluxos:
        chaves.alterar(admin, chaves.nome_fluxo(fluxo), estado="ligada", modo=modo)


def _contato_ativo(c, *, testador=True) -> ContatoVerificado:
    op = c.usuarios["operador"]
    contato = contatos.cadastrar(op, c.ps.servidor_id)
    contatos.confirmar_numero(op, contato.pk)
    contatos.registrar_optin(op, contato.pk, ContatoVerificado.OrigemOptin.FORMULARIO)
    if testador:
        contatos.autorizar_testador(c.usuarios["admin"], E164, "Testador 1")
    return ContatoVerificado.objects.get(pk=contato.pk)


def _liberar(c, dias_prazo=5):
    hoje = timezone.localdate()
    return prestacao.salvar_solicitacao(c.usuarios["operador"], c.ps.pk, numero="2026/0001",
                                        liberacao=hoje, prazo=hoje + timedelta(days=dias_prazo))


def _processar_entradas():
    while entrada.processar_uma_entrada():
        pass


def _aviso(c) -> Comunicacao:
    return Comunicacao.objects.get(tipo=viagens_whatsapp.AVISO,
                                   recurso=f"{viagens_whatsapp.RECURSO}:{c.ps.pk}")


TODOS = ("diarias_liberadas", "lembretes_comprovante", "respostas_automaticas",
         "recebimento_automatico", "atendimento")


# ------------------------------------------------------------------ o fluxo completo
def test_liberacao_whatsapp_comprovante_e_lembretes_encerrados(c):
    _ligar(c, *TODOS)
    contato = _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    assert aviso.situacao == S.AGENDADA and aviso.contato_id == contato.pk
    assert aviso.criada_por == c.usuarios["operador"]

    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)
    aviso.refresh_from_db()
    assert aviso.situacao == S.ENVIADA and aviso.mensagem_id.startswith("wamid.SIM.")
    assert len(espiao.envios) == 1 and espiao.envios[0].para == E164
    assert "dados fictícios" in espiao.envios[0].texto
    assert espiao.envios[0].modelo is not None  # fora da janela de 24 h: modelo
    assert aviso.tentativas_entrega.get().resultado == "aceita"

    # Status pelo webhook (simulado), fora de ordem: lida antes de entregue.
    simulador.simular_status(c.usuarios["operador"], aviso.pk, "lida")
    simulador.simular_status(c.usuarios["operador"], aviso.pk, "entregue")
    _processar_entradas()
    aviso.refresh_from_db()
    assert aviso.entrega == "lida" and aviso.lida_em and aviso.entregue_em

    # O servidor responde com o comprovante (PDF fictício), citando o aviso.
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, texto="Segue",
                               conteudo=PDF, nome="comprovante.pdf")
    _processar_entradas()
    r = Recebimento.objects.get()
    assert r.situacao == Recebimento.Situacao.IDENTIFICADO and r.servidor_id == c.ps.servidor_id
    assert r.comunicacao_id == aviso.pk
    assert recebimentos.processar_um()
    r.refresh_from_db()
    assert r.situacao == Recebimento.Situacao.ASSOCIADO, r.motivo
    anexo = AnexoPrestacao.objects.get(servidor=c.ps, tipo="comprovante", removido_em=None)
    assert r.referencia == f"viagens.anexoprestacao:{anexo.pk}"
    assert anexo.enviado_por == c.usuarios["operador"]  # em nome de quem originou

    # Confirmação ao servidor, dentro da janela (texto livre, citando a mensagem dele).
    confirmacao = Comunicacao.objects.get(tipo="automacao.confirmacao")
    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)
    confirmacao.refresh_from_db()
    assert confirmacao.situacao == S.ENVIADA
    assert espiao.envios[0].modelo is None and espiao.envios[0].responder_a == r.mensagem_id

    # Lembretes encerrados: nenhum novo, e a rotina do sino não cobra mais o saque.
    assert viagens_whatsapp.agendar_lembretes(c.ps.prazo_limite_saque) == 0
    from gestao.plataforma.models import Notificacao
    from gestao.viagens import avisos
    avisos.avisar_prazos(c.ps.prazo_limite_saque)
    assert not Notificacao.objects.filter(titulo__startswith="Saque vence").exists()
    # Conferir é outro passo, e a prestação continua aberta.
    recebimentos.conferir(c.usuarios["operador"], r.pk)
    r.refresh_from_db()
    c.ps.refresh_from_db()
    assert r.situacao == Recebimento.Situacao.CONFERIDO and not c.ps.finalizada


def test_lembrete_e_obsoleto_quando_o_comprovante_chega_antes(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c, dias_prazo=2)
    assert entrega.processar_uma(porta=Espiao())
    assert viagens_whatsapp.agendar_lembretes() == 1
    lembrete = Comunicacao.objects.get(tipo=viagens_whatsapp.LEMBRETE)
    from gestao.viagens import anexos
    anexos.anexar(c.usuarios["operador"], c.ps.prestacao_id, "comprovante",
                  servidor_pk=c.ps.pk, nome="c.pdf", conteudo=PDF)
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    lembrete.refresh_from_db()
    assert lembrete.situacao == S.OBSOLETA and espiao.envios == []


# ------------------------------------------------------------------ travas antes do envio
def test_fora_da_lista_de_testadores_zero_chamada(c):
    _ligar(c, *TODOS)
    _contato_ativo(c, testador=False)
    _liberar(c)
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    aviso = _aviso(c)
    assert espiao.envios == []
    assert aviso.situacao == S.RECUSADA and "testadores" in aviso.motivo
    assert ExcecaoAutomacao.objects.filter(comunicacao=aviso, tipo="contato").exists()


def test_sem_optin_zero_chamada(c):
    _ligar(c, *TODOS)
    contato = contatos.cadastrar(c.usuarios["operador"], c.ps.servidor_id)
    contatos.confirmar_numero(c.usuarios["operador"], contato.pk)
    contatos.autorizar_testador(c.usuarios["admin"], E164, "Testador 1")
    _liberar(c)
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    assert espiao.envios == [] and _aviso(c).situacao == S.RECUSADA


def test_telefone_do_cadastro_mudou_zero_chamada(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    c.ps.servidor.telefone = "41988887777"
    c.ps.servidor.save(update_fields=["telefone"])
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    assert espiao.envios == [] and "telefone" in _aviso(c).motivo


def test_chave_desligada_nada_sai_e_ao_religar_sai(c):
    _contato_ativo(c)
    _liberar(c)
    espiao = Espiao()
    assert not entrega.processar_uma(porta=espiao)
    assert _aviso(c).situacao == S.AGENDADA and espiao.envios == []
    _ligar(c, *TODOS)
    chaves.desligar_tudo(c.usuarios["admin"], "teste")
    assert not entrega.processar_uma(porta=espiao)
    chaves.alterar(c.usuarios["admin"], chaves.GERAL, estado="ligada")
    assert entrega.processar_uma(porta=espiao)
    assert len(espiao.envios) == 1


def test_modo_assistido_pede_aprovacao_e_sombra_nao_envia(c):
    _ligar(c, "diarias_liberadas", modo="assistido")
    _contato_ativo(c)
    _liberar(c)
    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)  # o modo vale na hora do envio
    aviso = _aviso(c)
    assert aviso.situacao == S.AGUARDANDO_APROVACAO and espiao.envios == []
    assert not entrega.processar_uma(porta=espiao)
    comunicacoes.aprovar(c.usuarios["operador"], aviso.pk)
    assert entrega.processar_uma(porta=espiao)
    assert len(espiao.envios) == 1
    # Sombra: prepara e registra, sem envio.
    chaves.alterar(c.usuarios["admin"], chaves.nome_fluxo("lembretes_comprovante"),
                   estado="ligada", modo="sombra")
    hoje = timezone.localdate()
    prestacao.salvar_solicitacao(c.usuarios["operador"], c.ps.pk, numero="2026/0001",
                                 liberacao=hoje, prazo=hoje + timedelta(days=2))
    viagens_whatsapp.agendar_lembretes()
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    assert Comunicacao.objects.get(tipo=viagens_whatsapp.LEMBRETE).situacao == S.SOMBRA
    assert all(m.texto.find("Lembrete") < 0 for m in espiao.envios)


def test_mudar_a_liberacao_deixa_o_aviso_antigo_obsoleto(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c, dias_prazo=5)
    _liberar(c, dias_prazo=7)  # prazo corrigido antes de sair
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    situacoes = sorted(Comunicacao.objects.filter(tipo=viagens_whatsapp.AVISO)
                       .values_list("situacao", flat=True))
    assert situacoes == [S.ENVIADA, S.OBSOLETA] and len(espiao.envios) == 1


# ------------------------------------------------------------------ resultados
def test_resultado_incerto_nunca_reenvia_e_a_meta_resolve_pela_referencia(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    comunicacoes.simular_proxima(c.usuarios["operador"], aviso.pk, "incerta")
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    aviso.refresh_from_db()
    assert aviso.situacao == S.INCERTA and len(espiao.envios) == 1
    assert ExcecaoAutomacao.objects.filter(comunicacao=aviso, tipo="resultado_incerto",
                                           situacao="aberta").exists()
    assert not entrega.processar_uma(porta=espiao)  # nada de reenvio automático
    # A Meta manda o status com a nossa referência: saiu, sim.
    corpo = webhook.montar_status(mensagem_id="wamid.REAL1", status="sent",
                                  destinatario=E164, referencia=f"com:{aviso.pk}:t1")
    entrada.registrar_entrada(corpo)
    _processar_entradas()
    aviso.refresh_from_db()
    assert aviso.situacao == S.ENVIADA and aviso.mensagem_id == "wamid.REAL1"
    assert not ExcecaoAutomacao.objects.filter(comunicacao=aviso, situacao="aberta").exists()


def test_reserva_vencida_vira_incerta(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    reserva = entrega.reservar()
    assert reserva is not None  # o processo "morre" aqui, sem enviar
    Comunicacao.objects.filter(pk=reserva.comunicacao_id).update(
        reservada_ate=timezone.now() - timedelta(seconds=1))
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    assert Comunicacao.objects.get(pk=reserva.comunicacao_id).situacao == S.INCERTA
    assert espiao.envios == []


def test_falha_temporaria_volta_com_espera_e_tem_limite(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    for rodada in range(1, 4):
        comunicacoes.simular_proxima(c.usuarios["operador"], aviso.pk, "temporaria")
        Comunicacao.objects.filter(pk=aviso.pk).update(proxima_tentativa_em=timezone.now())
        entrega.processar_uma(porta=Espiao())
        aviso.refresh_from_db()
        assert aviso.tentativas == rodada
    assert aviso.situacao == S.FALHOU
    assert ExcecaoAutomacao.objects.filter(comunicacao=aviso, tipo="falha_definitiva").exists()


def test_registrar_resultado_e_idempotente(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    reserva = entrega.reservar()
    envio = AdaptadorSimulado().enviar(reserva.mensagem)
    entrega.registrar_resultado(reserva.tentativa_id, envio=envio)
    entrega.registrar_resultado(reserva.tentativa_id, envio=envio)
    assert Comunicacao.objects.get(pk=reserva.comunicacao_id).situacao == S.ENVIADA
    assert Comunicacao.objects.get(pk=reserva.comunicacao_id).tentativas_entrega.count() == 1


# ------------------------------------------------------------------ entrada
def test_webhook_duplicado_e_status_repetido(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    corpo = webhook.montar_status(mensagem_id=aviso.mensagem_id, status="delivered",
                                  destinatario=E164)
    _, criada = entrada.registrar_entrada(corpo)
    _, de_novo = entrada.registrar_entrada(corpo)
    assert criada and not de_novo and EntradaWebhook.objects.count() == 1
    outro = webhook.montar_status(mensagem_id=aviso.mensagem_id, status="delivered",
                                  destinatario=E164, quando=timezone.now() + timedelta(seconds=3))
    entrada.registrar_entrada(outro)
    _processar_entradas()
    assert StatusEntrega.objects.filter(mensagem_id=aviso.mensagem_id).count() == 1
    falha = webhook.montar_status(mensagem_id=aviso.mensagem_id, status="failed",
                                  destinatario=E164, erro_codigo="131026")
    entrada.registrar_entrada(falha)
    _processar_entradas()
    aviso.refresh_from_db()
    assert aviso.entrega == "entregue" and aviso.situacao == S.ENVIADA  # entregue prevalece


def test_numero_desconhecido_fica_em_quarentena_sem_download(c):
    _ligar(c, *TODOS)
    corpo = webhook.montar_mensagem(mensagem_id="wamid.X1", remetente="5541911112222",
                                    texto="oi, segue o comprovante")
    entrada.registrar_entrada(corpo)
    _processar_entradas()
    r = Recebimento.objects.get()
    assert r.situacao == Recebimento.Situacao.QUARENTENA and r.servidor_id is None
    assert ExcecaoAutomacao.objects.filter(tipo="remetente_desconhecido").exists()
    assert not recebimentos.processar_um()
    assert not Comunicacao.objects.exists()  # ninguém responde a número desconhecido


def test_arquivo_invalido_e_recusado_com_motivo(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=b"MZ\x90\x00exe",
                               nome="comprovante.pdf")
    _processar_entradas()
    recebimentos.processar_um()
    r = Recebimento.objects.get()
    assert r.situacao == Recebimento.Situacao.RECUSADO and "PDF" in r.motivo
    assert not AnexoPrestacao.objects.filter(servidor=c.ps, tipo="comprovante").exists()
    assert Comunicacao.objects.filter(tipo="automacao.arquivo_recusado").exists()


def test_sair_revoga_e_aceito_registra_optin(c):
    _ligar(c, *TODOS)
    op = c.usuarios["operador"]
    contato = contatos.cadastrar(op, c.ps.servidor_id)
    contatos.autorizar_testador(c.usuarios["admin"], E164, "Testador 1")
    entrada.registrar_entrada(webhook.montar_mensagem(mensagem_id="wamid.A1", remetente=E164,
                                                      texto="Aceito"))
    _processar_entradas()
    contato.refresh_from_db()
    assert contato.ativo and contato.metodo == "mensagem" and contato.optin_origem == "mensagem"
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    assert Comunicacao.objects.get(tipo="automacao.boas_vindas").situacao == S.ENVIADA
    entrada.registrar_entrada(webhook.montar_mensagem(mensagem_id="wamid.A2", remetente=E164,
                                                      texto="SAIR"))
    _processar_entradas()
    contato.refresh_from_db()
    assert contato.revogado_em is not None
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    # A confirmação do descadastro sai uma vez, mesmo com o contato já revogado.
    assert len(espiao.envios) == 1
    assert Comunicacao.objects.get(tipo="automacao.descadastro").situacao == S.ENVIADA


def test_sem_comunicacao_aberta_uma_pessoa_escolhe_o_destino(c):
    _ligar(c, *TODOS)
    contato = _contato_ativo(c)
    _liberar(c)
    Comunicacao.objects.update(situacao=S.CANCELADA)  # nenhuma comunicação aberta
    conteudo = PDF
    midia, mime, sha = simulador._guardar_midia(conteudo)
    from gestao.integracoes.whatsapp.porta import Anexo
    entrada.registrar_entrada(webhook.montar_mensagem(
        mensagem_id="wamid.D1", remetente=contato.endereco,
        anexo=Anexo(midia_id=midia, tipo="document", mime=mime, sha256=sha, nome="c.pdf")))
    _processar_entradas()
    recebimentos.processar_um()
    r = Recebimento.objects.get()
    assert r.situacao == Recebimento.Situacao.IDENTIFICADO and r.arquivo
    assert ExcecaoAutomacao.objects.filter(recebimento=r, tipo="associacao").exists()
    candidatos = recebimentos.candidatos(r)
    assert len(candidatos) == 1
    d, cand = candidatos[0]
    recebimentos.associar_manual(c.usuarios["operador"], r.pk, d.chave, cand.recurso)
    r.refresh_from_db()
    assert r.situacao == Recebimento.Situacao.ASSOCIADO
    assert r.associado_por == c.usuarios["operador"]


# ------------------------------------------------------------------ webhook HTTP
REAL = {"modo": "cloud_api", "phone_number_id": "123", "access_token": "tok",
        "app_secret": "segredo-de-teste", "verify_token": "verifica"}


def test_webhook_sem_canal_real_recusa_tudo(client):
    assert client.post("/integracoes/whatsapp/webhook/", b"{}",
                       content_type="application/json").status_code == 401
    assert client.get("/integracoes/whatsapp/webhook/", {"hub.mode": "subscribe",
                      "hub.verify_token": "x", "hub.challenge": "1"}).status_code == 403


@override_settings(WHATSAPP=REAL)
def test_webhook_assinatura_e_verificacao(client):
    url = "/integracoes/whatsapp/webhook/"
    r = client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "verifica",
                         "hub.challenge": "desafio123"})
    assert r.status_code == 200 and r.content == b"desafio123"
    assert client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "errado",
                            "hub.challenge": "x"}).status_code == 403
    corpo = webhook.montar_status(mensagem_id="wamid.Z", status="sent", destinatario=E164)
    assert client.post(url, corpo, content_type="application/json",
                       HTTP_X_HUB_SIGNATURE_256="sha256=" + "0" * 64).status_code == 401
    assert not EntradaWebhook.objects.exists()
    ok = client.post(url, corpo, content_type="application/json",
                     HTTP_X_HUB_SIGNATURE_256=webhook.assinar(corpo, "segredo-de-teste"))
    assert ok.status_code == 200 and EntradaWebhook.objects.count() == 1
    # Reentrega da Meta: 200 de novo, sem duplicar.
    assert client.post(url, corpo, content_type="application/json",
                       HTTP_X_HUB_SIGNATURE_256=webhook.assinar(corpo, "segredo-de-teste")
                       ).status_code == 200
    assert EntradaWebhook.objects.count() == 1


def test_telas_da_automacao(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    op = Client()
    op.force_login(c.usuarios["operador"])
    for nome, args in (("painel", []), ("comunicacoes", []), ("comunicacao", [aviso.pk]),
                       ("recebimentos", []), ("excecoes", []), ("contatos", []),
                       ("novo_contato", [])):
        r = op.get(reverse(f"automacao:{nome}", args=args))
        assert r.status_code == 200, nome
    assert op.get(reverse("automacao:canal")).status_code == 403
    assert op.get(reverse("automacao:testadores")).status_code == 403
    admin = Client()
    admin.force_login(c.usuarios["admin"])
    assert admin.get(reverse("automacao:canal")).status_code == 200
    assert admin.get(reverse("automacao:testadores")).status_code == 200
    # Outra unidade não vê a comunicação (404), e quem não tem o módulo leva 403.
    outra = Client()
    outra.force_login(c.usuarios["outra"])
    assert outra.get(reverse("automacao:comunicacao", args=[aviso.pk])).status_code == 404
    consulta = Client()
    consulta.force_login(c.usuarios["consulta"])
    assert consulta.get(reverse("automacao:painel")).status_code == 403


def test_duvida_em_texto_livre_responde_com_o_assistente(c):
    _ligar(c, *TODOS, "assistente_whatsapp")
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    entrada.registrar_entrada(webhook.montar_mensagem(
        mensagem_id="wamid.Q1", remetente=E164, texto="Qual é o meu prazo de saque?"))
    _processar_entradas()
    r = Recebimento.objects.get(mensagem_id="wamid.Q1")
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    resposta = Comunicacao.objects.get(tipo="automacao.assistente")
    assert resposta.situacao == S.ENVIADA and resposta.em_resposta_a == r
    c.ps.refresh_from_db()
    assert f"{c.ps.prazo_limite_saque:%d/%m/%Y}" in espiao.envios[-1].texto
    # Pedido de ação: o assistente recusa e encaminha à equipe.
    entrada.registrar_entrada(webhook.montar_mensagem(
        mensagem_id="wamid.Q2", remetente=E164, texto="cancele minha viagem"))
    _processar_entradas()
    r2 = Recebimento.objects.get(mensagem_id="wamid.Q2")
    assert r2.situacao == Recebimento.Situacao.ENCAMINHADO
    assert ExcecaoAutomacao.objects.filter(recebimento=r2, tipo="atendimento").exists()


def test_sem_o_fluxo_do_assistente_a_duvida_vai_para_a_equipe(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    entrada.registrar_entrada(webhook.montar_mensagem(
        mensagem_id="wamid.Q3", remetente=E164, texto="Qual é o meu prazo?"))
    _processar_entradas()
    assert Recebimento.objects.get(mensagem_id="wamid.Q3").situacao == "encaminhado"
    assert not Comunicacao.objects.filter(tipo="automacao.assistente").exists()
