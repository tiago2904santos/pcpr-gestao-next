"""Dados de demonstração da automação para o PREVIEW (canal SEMPRE simulado — ADR 0046).

Monta o que uma pessoa precisa ver para avaliar as telas: chaves ligadas no modo
automático, contatos verificados com opt-in de alguns servidores (números sintéticos do DEMO,
que nunca recebem nada: não há Cloud API no PREVIEW), a lista de testadores, avisos de
diárias enviados e lidos, um comprovante devolvido e associado, uma mensagem de número
desconhecido em quarentena, uma dúvida respondida pelo assistente, um resultado desconhecido
na fila de exceções e uma credencial de exemplo (revogada: o valor nunca é mostrado).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import date

from django.db import connection
from django.utils import timezone

from gestao.cadastros.models import Servidor
from gestao.integracoes.whatsapp import config as whatsapp_config
from gestao.integracoes.whatsapp import webhook
from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado
from gestao.integracoes.whatsapp.porta import Anexo
from gestao.plataforma import ambiente

from . import chaves, comunicacoes, dominio, entrada, entrega, recebimentos, simulador
from .models import Comunicacao, ContatoVerificado, DestinatarioAutorizado

TABELAS = (
    "automacao_pedidoaprovacao", "automacao_execucaoferramenta", "automacao_delegacao",
    "automacao_registroidempotencia", "automacao_credencialintegracao",
    "automacao_eventointegracao", "automacao_linkacesso", "automacao_excecaoautomacao",
    "automacao_conteudorecebimento", "automacao_statusentrega", "automacao_tentativaentrega",
    "automacao_conteudocomunicacao", "automacao_comunicacao", "automacao_recebimento",
    "automacao_entradawebhook", "automacao_destinatarioautorizado",
    "automacao_contatoverificado", "automacao_chaveautomacao",
)
FLUXOS = ("diarias_liberadas", "lembretes_comprovante", "respostas_automaticas",
          "recebimento_automatico", "atendimento", "assistente_whatsapp", "km_vespera",
          "ferramentas")
PDF_DEMO = (b"%PDF-1.4\n% comprovante ficticio do PREVIEW (DEMO), sem valor\n"
            b"1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")


def limpar() -> None:
    with connection.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE")


def _rodar_worker() -> None:
    """O worker, na transação do seed: só com o adaptador simulado (sem rede)."""
    if whatsapp_config.carregar().real:
        raise RuntimeError("A demonstração só roda com o canal simulado.")
    antes = entrega.VERIFICAR_TRANSACAO
    entrega.VERIFICAR_TRANSACAO = False
    try:
        for _ in range(200):
            feito = entrada.processar_uma_entrada()
            feito = recebimentos.processar_um(AdaptadorSimulado()) or feito
            feito = entrega.processar_uma(porta=AdaptadorSimulado()) or feito
            if not feito:
                break
    finally:
        entrega.VERIFICAR_TRANSACAO = antes


def semear(demo, hoje: date) -> dict[str, int]:
    ambiente.exigir_ambiente_de_demonstracao("semear a automação de demonstração")
    # As tabelas já foram limpas no começo do seed (viagens.demonstracao.TABELAS): os avisos
    # de diárias agendados pelo seed de Viagens ficam e ganham contato aqui.
    for nome in (chaves.GERAL, chaves.nome_canal("whatsapp"),
                 *(chaves.nome_fluxo(f) for f in FLUXOS)):
        chaves.alterar(demo, nome, estado="ligada", modo="automatico",
                       motivo="Demonstração (canal simulado).")
    # Os avisos de diárias que o seed de Viagens agendou: quem tem telefone ganha contato.
    agora = timezone.now()
    servidores = list(dict.fromkeys(
        Comunicacao.objects.filter(tipo="viagens.diarias_liberadas")
        .exclude(servidor__telefone="").values_list("servidor_id", flat=True)))[:4]
    contatos = []
    for i, servidor_id in enumerate(servidores):
        s = Servidor.objects.get(pk=servidor_id)
        endereco = dominio.e164_do_brasil(s.telefone)
        if not endereco:
            continue
        contato = ContatoVerificado.objects.create(
            servidor=s, endereco=endereco, verificado_em=agora,
            metodo=ContatoVerificado.Metodo.SIMULADO, optin_em=agora,
            optin_origem=ContatoVerificado.OrigemOptin.SIMULADO, optin_versao="demo",
            criado_por=demo)
        DestinatarioAutorizado.objects.create(endereco=endereco,
                                              descricao=f"Testador DEMO {i + 1} (fictício)",
                                              adicionado_por=demo)
        contatos.append(contato)
    for c in Comunicacao.objects.filter(contato__isnull=True, servidor_id__in=servidores):
        c.contato = next((x for x in contatos if x.servidor_id == c.servidor_id), None)
        c.save(update_fields=["contato"])
    _rodar_worker()
    enviadas = list(Comunicacao.objects.filter(tipo="viagens.diarias_liberadas",
                                               situacao=Comunicacao.Situacao.ENVIADA)
                    .order_by("pk"))
    for c in enviadas[:3]:
        simulador.simular_status(demo, c.pk, "entregue")
        simulador.simular_status(demo, c.pk, "lida")
    if enviadas:
        aviso = enviadas[0]
        # Um comprovante devolvido pelo WhatsApp, associado à prestação certa…
        simulador.simular_resposta(demo, aviso.pk, texto="Segue o comprovante",
                                   conteudo=PDF_DEMO, nome="comprovante-demo.pdf")
        # …uma dúvida que o assistente (sem IA) responde…
        simulador.simular_resposta(demo, aviso.pk, texto="Qual é o meu prazo de saque?")
        # …e um pedido de ajuda cuja resposta fica com resultado desconhecido (exceção).
        simulador.simular_resposta(demo, aviso.pk, texto="AJUDA")
        while entrada.processar_uma_entrada():
            pass
        ajuda = Comunicacao.objects.filter(tipo="automacao.ajuda").first()
        if ajuda is not None:
            comunicacoes.simular_proxima(demo, ajuda.pk, "incerta")
    sha = base64.b64encode(hashlib.sha256(PDF_DEMO).digest()).decode()
    entrada.registrar_entrada(webhook.montar_mensagem(
        mensagem_id="wamid.DEMO.DESCONHECIDO", remetente="5541900000000",
        texto="Olá, segue o comprovante (número desconhecido)",
        anexo=Anexo(midia_id="DEMOAUSENTE", tipo="document", mime="application/pdf",
                    sha256=sha, nome="x.pdf")), origem="simulador")
    _rodar_worker()
    # As exceções ficam na fila; o sino do DEMO guarda só os avisos de exemplo "(DEMO)".
    from gestao.plataforma.models import Notificacao

    Notificacao.objects.filter(titulo__startswith="Automação:").delete()
    from .api import credenciais

    cred, _ = credenciais.emitir(demo, nome="n8n do LAB (exemplo, revogada)",
                                 tipo="transporte", dias=30)
    credenciais.revogar(demo, cred.pk)
    return {"contatos": len(contatos), "comunicacoes": Comunicacao.objects.count()}
