"""E-mail ao fornecedor (paridade com o envio da OS e da OB da referência): a tela abre já
preenchida — para (o e-mail do fornecedor), cópia (a ASCOM, da configuração), assunto e
texto da configuração com os campos trocados pelos dados da OS — e tudo se edita antes de
enviar. Sai pelo servidor de e-mail configurado (`MAILERS`; sem SMTP, só no console/log),
com o PDF anexo, e cada envio fica no histórico.

- OS: só sem pendência (nº, local, quem recebe) e não cancelada; marca "OS enviada em".
- OB: com o PDF e a data da ordem bancária; se o próximo marco é o envio à empresa, grava a
  data de hoje (em todas as OS do pagamento conjunto) e o pagamento se conclui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from . import conjunto, documentos, financeiro, policies, vias
from . import dominio_pedido as regras
from .models import ConfiguracaoOficio, Movimento, Solicitacao
from .pedidos import PedidoInvalido

QUAIS = {"os": "Ordem de serviço", "ob": "Ordem bancária"}
CAMPOS = ("numero", "evento", "data", "horario", "local", "responsavel", "quantidade",
          "fornecedor", "nota", "ordem_bancaria", "data_ordem_bancaria")
A_COMBINAR = "a combinar"
MSG_SEM_EMAIL = "Informe o e-mail do fornecedor."
MSG_SEM_ASSUNTO = "Informe o assunto do e-mail."
MSG_FALHA = ("O e-mail não foi enviado: o servidor de e-mail recusou ou não respondeu ({erro}). "
             "Tente de novo.")
_R_SEPARADOR = re.compile(r"[,;\s]+")
_R_CAMPO = re.compile(r"\{([a-z_]+)\}")


@dataclass
class Rascunho:
    qual: str
    para: str
    copia: str
    assunto: str
    texto: str
    anexo: str
    problemas: list[str] = field(default_factory=list)
    enviado_em: datetime | date | None = None
    sem_email_fornecedor: bool = False


# ---------------------------------------------------------------- regras puras
def enderecos(texto: str) -> list[str]:
    """"a@x, b@y; a@x" → [a@x, b@y] (sem repetir, na ordem); inválido levanta ValueError."""
    saida: list[str] = []
    for item in _R_SEPARADOR.split(texto or ""):
        item = item.strip()
        if not item:
            continue
        try:
            validate_email(item)
        except ValidationError:
            raise ValueError(f"E-mail inválido: {item}") from None
        if item.lower() not in (x.lower() for x in saida):
            saida.append(item)
    return saida


def preencher(modelo: str, valores: dict[str, str]) -> str:
    """Troca {campo} pelo valor; campo desconhecido fica como está."""
    return _R_CAMPO.sub(lambda m: valores.get(m.group(1), m.group(0)), modelo or "")


def _juntar(itens: list[str]) -> str:
    itens = [i for i in dict.fromkeys(itens) if i]
    if len(itens) < 2:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


# ---------------------------------------------------------------- dados da OS
def valores(s: Solicitacao) -> dict[str, str]:
    grupo = conjunto.membros(s) if conjunto.em_grupo(s) else [s]
    return {
        "numero": s.numero or "—",
        "evento": s.descricao,
        "data": f"{s.data_evento:%d/%m/%Y}" if s.data_evento else A_COMBINAR,
        "horario": f"{s.horario:%H:%M}" if s.horario else A_COMBINAR,
        "local": s.local_entrega or A_COMBINAR,
        "responsavel": s.responsavel or A_COMBINAR,
        "quantidade": str(s.quantidade),
        "fornecedor": str(s.lote.contrato.fornecedor),
        "nota": _juntar([x.nota_fiscal for x in grupo]) or "—",
        "ordem_bancaria": s.ob_numero or "—",
        "data_ordem_bancaria": (f"{s.ordem_bancaria_em:%d/%m/%Y}" if s.ordem_bancaria_em
                                else "—"),
    }


def problemas(s: Solicitacao, qual: str) -> list[str]:
    if s.cancelada:
        return ["A solicitação está cancelada."]
    if qual == "os":
        return documentos.pendencias("os", s)
    faltas = []
    if not s.ob_pdf:
        faltas.append("Anexe o PDF da ordem bancária (seção dos PDFs).")
    if not s.ordem_bancaria_em:
        faltas.append("Registre a data da ordem bancária.")
    return faltas


def _nome_anexo(s: Solicitacao, qual: str) -> str:
    if qual == "os":
        return documentos.nome_do_arquivo("os", s)
    return f"Ordem bancaria {s.ob_numero or s.numero or s.pk}.pdf"


def _ultimo_envio(s: Solicitacao, qual: str) -> datetime | date | None:
    if qual == "os":
        return s.os_enviada_em
    m = (s.movimentos.filter(acao=Movimento.Acao.EMAIL, texto__startswith=QUAIS["ob"])
         .order_by("-em").first())
    return m.em if m else None


def rascunho(s: Solicitacao, qual: str) -> Rascunho:
    cfg = ConfiguracaoOficio.atual()
    v = valores(s)
    fornecedor = s.lote.contrato.fornecedor
    para = fornecedor.email or ""
    try:
        copia = [x for x in enderecos(cfg.emails_ascom)
                 if x.lower() not in (para.lower(),)]
    except ValueError:
        copia = []
    assunto = cfg.assunto_email_os if qual == "os" else cfg.assunto_email_ob
    texto = cfg.texto_email_os if qual == "os" else cfg.texto_email_ob
    return Rascunho(qual=qual, para=para, copia=", ".join(copia),
                    assunto=" ".join(preencher(assunto, v).split()),
                    texto=preencher(texto, v), anexo=_nome_anexo(s, qual),
                    problemas=problemas(s, qual), enviado_em=_ultimo_envio(s, qual),
                    sem_email_fornecedor=not para)


# ---------------------------------------------------------------- envio
def _anexo(usuario, s: Solicitacao, qual: str) -> tuple[str, bytes]:
    if qual == "os":
        arq = vias.obter(usuario, s, "os")
        return arq.nome, arq.conteudo
    with s.ob_pdf.open("rb") as f:
        return _nome_anexo(s, qual), f.read()


def enviar(usuario, pk: int, qual: str, *, para: str, copia: str, assunto: str,
           texto: str, hoje: date | None = None) -> Solicitacao:
    """Envia agora (síncrono: o erro do servidor volta na tela) e registra no histórico."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    if qual not in QUAIS:
        raise PedidoInvalido("Envio desconhecido.")
    try:
        destinos = enderecos(para)
        copias = [x for x in enderecos(copia) if x.lower() not in {d.lower() for d in destinos}]
    except ValueError as exc:
        raise PedidoInvalido(str(exc)) from None
    if not destinos:
        raise PedidoInvalido(MSG_SEM_EMAIL)
    assunto = " ".join((assunto or "").split())[:200]
    if not assunto:
        raise PedidoInvalido(MSG_SEM_ASSUNTO)
    hoje = hoje or timezone.localdate()
    with transaction.atomic():
        s = Solicitacao.objects.select_for_update().select_related(
            "lote__contrato__fornecedor").get(pk=pk)
        faltas = problemas(s, qual)
        if faltas:
            raise PedidoInvalido(" ".join(faltas))
        nome, conteudo = _anexo(usuario, s, qual)
        msg = EmailMessage(subject=assunto, body=texto or "", to=destinos, cc=copias,
                           reply_to=copias[:1] or None)
        msg.attach(nome, conteudo, "application/pdf")
        try:
            msg.send(fail_silently=False)
        except OSError as exc:  # SMTPException é OSError
            raise PedidoInvalido(MSG_FALHA.format(erro=exc.__class__.__name__)) from None
        agora = timezone.localtime()
        registro = (f"{QUAIS[qual]} enviada por e-mail em {agora:%d/%m/%Y} às {agora:%H:%M} "
                    f"para {', '.join(destinos)}"
                    + (f" (cópia: {', '.join(copias)})" if copias else "")
                    + f". Assunto: {assunto}. Anexo: {nome}.")
        grupo = conjunto.membros(s) if qual == "ob" and conjunto.em_grupo(s) else [s]
        for x in grupo:
            Movimento.objects.create(solicitacao=x, acao=Movimento.Acao.EMAIL, texto=registro,
                                     usuario=usuario)
        if qual == "os":
            s.os_enviada_em = agora
            s.save(update_fields=["os_enviada_em", "atualizado_em"])
        else:
            marco = regras.proximo_marco(s.valores_dos_marcos, s.cancelada)
            if marco and marco[0] == "envio_empresa_em" and not s.bloqueada:
                s = financeiro.registrar_marco(usuario, s.pk, f"{hoje:%d/%m/%Y}",
                                               "Ordem bancária enviada por e-mail.", hoje=hoje)
    return s
