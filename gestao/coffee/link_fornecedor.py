"""Link do fornecedor (paridade com o link da referência): pela OS, a equipe manda por
e-mail um link que vale 30 dias; por ele, sem login, o fornecedor envia o PDF da nota
fiscal e das certidões, e a equipe confere — aceito, a nota entra na OS e a certidão nas
do fornecedor; recusado, ele pode mandar de novo.

Segurança: o token (`secrets.token_urlsafe(32)`) só existe no e-mail; o banco guarda o
SHA-256. Token fora do tamanho nem consulta o banco; desconhecido, vencido ou revogado
dão a mesma resposta. Limites por hora: 30 envios por link e por origem (IP em hash).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.notificacoes import notificar

from . import certidoes, pdfs, policies
from . import dominio_certidoes as regras_certidoes
from . import dominio_leitura as leitura
from .certidoes import texto_do_pdf
from .forms import conferir_pdf
from .models import EnvioFornecedor, LinkFornecedor, Movimento, Solicitacao
from .pedidos import PedidoInvalido

DIAS = 30
TAMANHO_MINIMO, TAMANHO_MAXIMO = 32, 128
LIMITE_POR_HORA = 30
MSG_LIMITE = "Muitos envios em pouco tempo. Tente de novo daqui a uma hora."
MSG_INDISPONIVEL = "Não dá para gerar link para uma OS cancelada ou com o pagamento concluído."


@dataclass
class Situacao:
    """O que o fornecedor vê: a nota e cada certidão."""
    nota: str
    certidoes: list[tuple[str, str]]  # (rótulo, situação)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def origem(ip: str) -> str:
    """O IP em hash (com o segredo do sistema): basta para o limite, não identifica."""
    return _hash(f"{settings.SECRET_KEY}:{ip or ''}")[:32]


def ativo(s: Solicitacao) -> LinkFornecedor | None:
    return (s.links_fornecedor.filter(revogado_em__isnull=True, expira_em__gt=timezone.now())
            .select_related("criado_por").first())


def disponivel(s: Solicitacao) -> bool:
    return not (s.cancelada or s.concluida)


def criar(usuario, s: Solicitacao, enviado_para: str) -> tuple[LinkFornecedor, str]:
    """Um link novo (o anterior deixa de valer). Chamado dentro da transação do envio: se o
    e-mail não sair, o link não fica. Devolve o link e o token em claro (só para o e-mail)."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    if not disponivel(s):
        raise PedidoInvalido(MSG_INDISPONIVEL)
    agora = timezone.now()
    s.links_fornecedor.filter(revogado_em__isnull=True).update(revogado_em=agora)
    token = secrets.token_urlsafe(32)
    link = LinkFornecedor.objects.create(
        solicitacao=s, token_hash=_hash(token), criado_por=usuario,
        expira_em=agora + timedelta(days=DIAS), enviado_para=enviado_para[:500])
    return link, token


def url_publica(token: str) -> str:
    return settings.URL_PUBLICA.rstrip("/") + reverse("fornecedor:envio", args=[token])


@transaction.atomic
def revogar(usuario, pk: int) -> int:
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    s = Solicitacao.objects.get(pk=pk)
    n = s.links_fornecedor.filter(revogado_em__isnull=True).update(revogado_em=timezone.now())
    if n:
        Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.EMAIL, usuario=usuario,
                                 texto="Link do fornecedor revogado.")
    return n


def do_token(token: str) -> LinkFornecedor | None:
    """O link vigente do token, ou None — sem dizer se não existe, venceu ou foi revogado."""
    if not token or not TAMANHO_MINIMO <= len(token) <= TAMANHO_MAXIMO:
        return None
    link = (LinkFornecedor.objects.select_related(
        "solicitacao__lote__contrato__fornecedor", "criado_por", "solicitacao__criado_por")
        .filter(token_hash=_hash(token)).first())
    if (link is None or link.revogado_em or link.expira_em <= timezone.now()
            or not disponivel(link.solicitacao)):
        return None
    return link


def situacao(link: LinkFornecedor, hoje: date | None = None) -> Situacao:
    hoje = hoje or timezone.localdate()
    s = link.solicitacao
    envios = list(s.envios_fornecedor.exclude(situacao=EnvioFornecedor.Situacao.RECUSADO))
    if s.nota_pdf:
        nota = "Já anexada pela ASCOM"
    elif any(e.tipo == EnvioFornecedor.Tipo.NOTA for e in envios):
        nota = "Recebida, aguardando conferência"
    else:
        nota = "Aguardando envio"
    vigentes = certidoes.vigentes(s.lote.contrato.fornecedor)
    linhas = []
    for tipo, rotulo in regras_certidoes.TIPOS:
        recebida = any(e.tipo == EnvioFornecedor.Tipo.CERTIDAO and e.tipo_certidao == tipo
                       and e.situacao == EnvioFornecedor.Situacao.RECEBIDO for e in envios)
        c = vigentes.get(tipo)
        if recebida:
            texto = "Recebida, aguardando conferência"
        elif c is None:
            texto = "Não enviada"
        elif c.validade < hoje:
            texto = f"Vencida em {c.validade:%d/%m/%Y} — envie a renovada"
        else:
            texto = f"Válida até {c.validade:%d/%m/%Y}"
        linhas.append((rotulo, texto))
    return Situacao(nota, linhas)


def _limite(link: LinkFornecedor, quem: str) -> None:
    desde = timezone.now() - timedelta(hours=1)
    recentes = EnvioFornecedor.objects.filter(recebido_em__gte=desde)
    if (recentes.filter(link=link).count() >= LIMITE_POR_HORA
            or recentes.filter(origem_hash=quem).count() >= LIMITE_POR_HORA):
        raise PedidoInvalido(MSG_LIMITE)


@transaction.atomic
def receber(link: LinkFornecedor, tipo: str, arquivo, *, tipo_certidao: str = "",
            validade_informada: date | None = None, ip: str = "",
            hoje: date | None = None) -> EnvioFornecedor:
    """O fornecedor manda a nota ou uma certidão: confere o PDF, lê o que dá e deixa à
    espera da conferência (uma nova do mesmo tipo substitui a ainda não conferida)."""
    hoje = hoje or timezone.localdate()
    link = LinkFornecedor.objects.select_for_update().select_related(
        "solicitacao__lote__contrato__fornecedor", "criado_por",
        "solicitacao__criado_por").get(pk=link.pk)
    s = link.solicitacao
    quem = origem(ip)
    _limite(link, quem)
    if tipo not in EnvioFornecedor.Tipo.values:
        raise PedidoInvalido("Escolha o que está enviando.")
    if tipo == EnvioFornecedor.Tipo.CERTIDAO and tipo_certidao not in regras_certidoes.ROTULOS:
        raise PedidoInvalido("Escolha o tipo da certidão.")
    if not arquivo:
        raise PedidoInvalido("Escolha o PDF.")
    try:
        conferir_pdf(arquivo)
    except ValidationError as exc:
        raise PedidoInvalido(" ".join(exc.messages)) from None
    fornecedor = s.lote.contrato.fornecedor
    texto = texto_do_pdf(arquivo)
    validade, lido, avisos = None, "", []
    if tipo == EnvioFornecedor.Tipo.NOTA:
        nota = leitura.ler_nota(texto)
        lido = " · ".join(p for p in (
            f"NF {nota.numero}" if nota.numero else "",
            f"R$ {nota.valor:.2f}".replace(".", ",") if nota.valor is not None else "",
            f"emitida em {nota.emissao:%d/%m/%Y}" if nota.emissao else "") if p)
        avisos = leitura.avisos_da_nota(
            nota, cnpj_fornecedor=fornecedor.cnpj, razao=fornecedor.razao_social,
            cnpj_formatado=fornecedor.cnpj_formatado, quantidade=s.quantidade_efetiva,
            unitario=s.valor_unitario, data_evento=s.data_evento, repetida_em="")
        rotulo = "Nota fiscal"
    else:
        rotulo = f"Certidão {regras_certidoes.ROTULOS[tipo_certidao]}"
        try:
            c = regras_certidoes.conferir(texto, tipo_certidao, fornecedor.cnpj,
                                          fornecedor.razao_social, fornecedor.cnpj_formatado,
                                          validade_informada)
        except ValueError as exc:
            raise PedidoInvalido(str(exc)) from None
        if c.validade < hoje:
            raise PedidoInvalido(f"Esta certidão venceu em {c.validade:%d/%m/%Y}: envie a "
                                 "renovada.")
        validade, lido = c.validade, f"válida até {c.validade:%d/%m/%Y}"
        avisos = [c.aviso] if c.aviso else []
    pendentes = s.envios_fornecedor.filter(tipo=tipo, situacao=EnvioFornecedor.Situacao.RECEBIDO)
    if tipo == EnvioFornecedor.Tipo.CERTIDAO:
        pendentes = pendentes.filter(tipo_certidao=tipo_certidao)
    pendentes.update(situacao=EnvioFornecedor.Situacao.RECUSADO,
                     motivo="Substituída por um envio mais novo.", conferido_em=timezone.now())
    arquivo.seek(0)
    envio = EnvioFornecedor.objects.create(
        link=link, solicitacao=s, tipo=tipo, tipo_certidao=tipo_certidao if tipo ==
        EnvioFornecedor.Tipo.CERTIDAO else "", arquivo=arquivo,
        nome_original=(getattr(arquivo, "name", "") or "")[:200], validade=validade,
        lido=lido[:255], avisos="\n".join(avisos), origem_hash=quem)
    Movimento.objects.create(
        solicitacao=s, acao=Movimento.Acao.FORNECEDOR, usuario=link.criado_por,
        texto=f"{rotulo} recebida pelo link do fornecedor" + (f" ({lido})." if lido else "."))
    notificar([link.criado_por, s.criado_por], f"{fornecedor} enviou: {rotulo.lower()}",
              f"{s} · {s.descricao[:80]}. Confira na solicitação.",
              reverse("coffee:solicitacao", args=[s.pk]) + "#envios-fornecedor")
    return envio


@transaction.atomic
def conferir(usuario, envio_pk: int, aceitar: bool, motivo: str = "") -> str:
    """Aceita (a nota entra na OS; a certidão, nas do fornecedor) ou recusa com o motivo."""
    if not policies.pode_acessar(usuario):
        raise PermissionDenied
    e = EnvioFornecedor.objects.select_for_update().select_related(
        "solicitacao__lote__contrato__fornecedor").get(pk=envio_pk)
    if e.situacao != EnvioFornecedor.Situacao.RECEBIDO:
        raise PedidoInvalido("Este envio já foi conferido.")
    s = e.solicitacao
    if s.bloqueada:
        raise PedidoInvalido("A solicitação está só para consulta: reabra para corrigir.")
    rotulo = str(e).split(" — ")[0]
    if aceitar:
        with e.arquivo.open("rb") as f:
            copia = ContentFile(f.read(), name=e.nome_original or "documento.pdf")
        if e.tipo == EnvioFornecedor.Tipo.NOTA:
            pdfs.anexar_nota(usuario, s.pk, copia)
        else:
            certidoes.anexar(usuario, s.lote.contrato.fornecedor_id, e.tipo_certidao, copia,
                             e.validade)
        e.situacao = EnvioFornecedor.Situacao.ACEITO
        mensagem = f"{rotulo} aceita."
    else:
        e.situacao = EnvioFornecedor.Situacao.RECUSADO
        e.motivo = " ".join((motivo or "").split())[:255]
        mensagem = f"{rotulo} recusada. O fornecedor pode enviar de novo pelo link."
    e.conferido_por, e.conferido_em = usuario, timezone.now()
    e.save()
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.FORNECEDOR, usuario=usuario,
                             texto=mensagem + (f" Motivo: {e.motivo}" if e.motivo else ""))
    return mensagem
