"""Tipos de comunicação da própria automação: respostas automáticas a quem escreveu
(confirmação de arquivo, ajuda, descadastro, boas-vindas, "encaminhei à equipe", arquivo
recusado) e a resposta escrita por uma pessoa da equipe.

Todos respondem a uma mensagem recebida — saem dentro da janela de 24 h, como texto livre.
Os textos dizem que é um sistema de testes e não falam em nome de órgão nenhum (ADR 0046).
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.urls import reverse

from . import ganchos
from .ganchos import Assunto, Preparo, TipoComunicacao

FLUXO_RESPOSTAS = "respostas_automaticas"
FLUXO_ATENDIMENTO = "atendimento"
FLUXO_ASSISTENTE = "assistente_whatsapp"


def _recebimento(contexto: dict):
    from .models import Recebimento

    pk = contexto.get("recebimento")
    return Recebimento.objects.filter(pk=pk).first() if isinstance(pk, int) else None


def _portal() -> str:
    return settings.URL_PUBLICA.rstrip("/") + "/"


def _confirmacao(contexto: dict) -> Preparo:
    from .models import Recebimento

    r = _recebimento(contexto)
    if r is None or r.situacao not in (Recebimento.Situacao.ASSOCIADO,
                                       Recebimento.Situacao.CONFERIDO):
        return Preparo(False, "O arquivo não está mais associado.")
    destino = ganchos.destino(r.destino)
    texto = destino.confirmacao(r.referencia) if destino else "Recebemos o seu arquivo."
    return Preparo(True, texto=texto, versao=f"r{r.pk}")


def _fixo(texto: str):
    def preparar(contexto: dict) -> Preparo:
        return Preparo(True, texto=texto)
    return preparar


def _ajuda(contexto: dict) -> Preparo:
    return Preparo(True, texto=(
        "Este é um sistema de testes com dados fictícios: nenhuma viagem, diária ou valor é "
        "real.\n\nPor aqui você recebe os avisos do teste e pode responder com a foto ou o "
        "PDF do comprovante quando for pedido. Para não receber mais mensagens, envie SAIR."
        f"\n\nPortal do teste: {_portal()}"))


def _recusado(contexto: dict) -> Preparo:
    r = _recebimento(contexto)
    motivo = (r.motivo if r else "") or "o arquivo não pôde ser lido"
    return Preparo(True, texto=(
        f"Não conseguimos aceitar o arquivo: {motivo.rstrip('.')}. Envie um PDF, JPG ou PNG de "
        "até 10 MB, por favor."))


def _resposta_humana(contexto: dict) -> Preparo:
    from .models import ConteudoComunicacao

    comunicacao_id = contexto.get("_comunicacao")
    # comunicacao_id é obrigatório: sem ele, o filtro não acharia conteúdo nenhum.
    conteudo = (ConteudoComunicacao.objects.filter(comunicacao_id=comunicacao_id).first()
                if comunicacao_id is not None else None)
    if conteudo is None or not conteudo.texto.strip():
        return Preparo(False, "A resposta escrita não está mais disponível (retenção).")
    return Preparo(True, texto=conteudo.texto)


def responder_com_assistente(recebimento) -> tuple[str, bool]:
    """(texto da resposta, precisa de uma pessoa?) — o mesmo assistente do portal (AUT-88),
    determinístico, só com a situação DO servidor identificado pelo contato verificado."""
    from gestao.assistencia import assistente

    conteudo = getattr(recebimento, "conteudo", None)
    pergunta = conteudo.texto if conteudo else ""
    r = assistente.responder(pergunta, recebimento.servidor_id)
    fontes = "; ".join(f.rotulo for f in r.fontes[:2])
    texto = r.texto + (f"\n\nFonte: {fontes}" if fontes else "")
    if r.sugerir_equipe:
        texto += "\n\nEncaminhei também para a equipe do teste."
    return texto, r.sugerir_equipe or r.categoria == "lacuna"


def _assistente(contexto: dict) -> Preparo:
    r = _recebimento(contexto)
    if r is None:
        return Preparo(False, "O recebimento não existe mais.")
    try:
        texto, _ = responder_com_assistente(r)
    except AttributeError:
        return Preparo(False, "A pergunta não está mais guardada (retenção).")
    return Preparo(True, texto=texto, versao=f"r{r.pk}")


def _assunto_recebimento(recurso: str) -> Assunto | None:
    _, _, pk = recurso.partition(":")
    if not pk.isdigit():
        return None
    return Assunto(f"Recebimento #{pk}", reverse("automacao:recebimento", args=[int(pk)]))


def registrar() -> None:
    curto = timedelta(hours=23)  # dentro da janela de atendimento
    for chave, rotulo, preparar, fluxo, exige_optin in (
        ("automacao.confirmacao", "Confirmação de arquivo recebido", _confirmacao,
         FLUXO_RESPOSTAS, True),
        ("automacao.ajuda", "Ajuda (resposta automática)", _ajuda, FLUXO_RESPOSTAS, True),
        ("automacao.descadastro", "Confirmação de descadastro", _fixo(
            "Pronto: você não vai receber mais mensagens deste sistema de testes. Se quiser "
            "voltar, fale com a equipe do teste."), FLUXO_RESPOSTAS, False),
        ("automacao.boas_vindas", "Boas-vindas (opt-in confirmado)", _fixo(
            "Obrigado! Seu número foi confirmado para receber os avisos deste sistema de "
            "testes (dados fictícios). Para sair a qualquer momento, envie SAIR."),
         FLUXO_RESPOSTAS, True),
        ("automacao.encaminhada", "Mensagem encaminhada à equipe", _fixo(
            "Recebemos a sua mensagem e encaminhamos à equipe do teste. A resposta vem por "
            "aqui."), FLUXO_RESPOSTAS, True),
        ("automacao.arquivo_recusado", "Arquivo recusado", _recusado, FLUXO_RESPOSTAS, True),
        ("automacao.resposta", "Resposta da equipe", _resposta_humana, FLUXO_ATENDIMENTO, True),
        ("automacao.assistente", "Resposta do assistente (sem IA)", _assistente,
         FLUXO_ASSISTENTE, True),
    ):
        ganchos.registrar_tipo(TipoComunicacao(
            chave=chave, rotulo=rotulo, fluxo=fluxo, preparar=preparar, validade=curto,
            assunto=_assunto_recebimento, exige_optin=exige_optin))
