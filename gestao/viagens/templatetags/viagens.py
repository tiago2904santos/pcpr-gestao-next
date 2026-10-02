"""Apresentação do domínio Viagens em templates (situação, prazo, faixas)."""

from __future__ import annotations

from datetime import datetime

from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

register = template.Library()

TOM_SITUACAO = {"rascunho": "neutro", "emitido": "sucesso", "cancelado": "perigo"}
ICONE_SITUACAO = {"rascunho": "file-pen-line", "emitido": "file-check-2", "cancelado": "ban"}


@register.filter
def tom_situacao(situacao: str) -> str:
    return TOM_SITUACAO.get(situacao, "neutro")


@register.filter
def icone_situacao(situacao: str) -> str:
    return ICONE_SITUACAO.get(situacao, "file-text")


@register.simple_tag
def contagem_dias(primeira_saida: datetime | None) -> dict[str, str] | None:
    """"faltam 7 dias" / "hoje" / "há 3 dias" (selo da lista)."""
    if not primeira_saida:
        return None
    dias = (timezone.localdate(primeira_saida) - timezone.localdate()).days
    if dias > 1:
        return {"texto": f"faltam {dias} dias", "tom": "aviso" if dias <= 10 else "info"}
    if dias == 1:
        return {"texto": "amanhã", "tom": "aviso"}
    if dias == 0:
        return {"texto": "hoje", "tom": "aviso"}
    return {"texto": f"há {-dias} dia{'s' if dias < -1 else ''}", "tom": "neutro"}


@register.filter
def periodo(trechos) -> str:
    trechos = list(trechos)
    if not trechos:
        return ""
    return formatar_periodo(trechos[0].saida_em, trechos[-1].chegada_em)


def formatar_periodo(saida: datetime | None, chegada: datetime | None) -> str:
    """"08/10 a 12/10/2026" (ou só a data, quando ida e volta são no mesmo dia)."""
    if not saida or not chegada:
        return ""
    ini = timezone.localtime(saida)
    fim = timezone.localtime(chegada)
    if ini.date() == fim.date():
        return f"{ini:%d/%m/%Y}"
    if ini.year == fim.year:
        return f"{ini:%d/%m} a {fim:%d/%m/%Y}"
    return f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}"


@register.filter
def destinos(oficio) -> str:
    vistos: list[str] = []
    for t in oficio.trechos.all():
        if t.destino_id != oficio.sede_id:
            rotulo = f"{t.destino.nome}/{t.destino.uf}"
            if rotulo not in vistos:
                vistos.append(rotulo)
    return ", ".join(vistos)


@register.filter
def data_iso(valor: str) -> str:
    """'2026-10-08T09:00:00-03:00' → '08/10/2026 09:00' (memória de cálculo)."""
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return valor or ""


@register.filter
def data_curta_iso(valor: str) -> str:
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor or ""


@register.filter
def secao_ok(prontidao, secao: str) -> bool:
    """Seção sem pendências bloqueantes (para o índice do formulário)."""
    if not prontidao:
        return False
    return not any(p.bloqueia and p.secao == secao for p in prontidao.pendencias)


@register.filter
def pendencias_da_secao(prontidao, secao: str):
    return prontidao.da_secao(secao) if prontidao else []


@register.filter
def selo_justificativa(oficio) -> dict[str, str] | None:
    """Selo da lista: justificativa pendente/preenchida quando o prazo a exige."""
    from ..dominio.prazos import avaliar_prazo

    saida = getattr(oficio, "primeira_saida", None)
    if oficio.situacao == "cancelado" or saida is None:
        return None
    try:
        prazo = oficio.unidade.configuracao.prazo_justificativa_dias
    except ObjectDoesNotExist:  # unidade sem configuração: as pendências já avisam
        return None
    avaliacao = avaliar_prazo(oficio.data_oficio, timezone.localdate(saida), prazo)
    if not avaliacao.justificativa_obrigatoria:
        return None
    if oficio.justificativa.strip():
        return {"texto": "Justificativa preenchida", "tom": "sucesso"}
    return {"texto": "Justificativa pendente", "tom": "aviso"}
