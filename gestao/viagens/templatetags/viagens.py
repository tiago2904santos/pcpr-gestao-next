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


@register.filter
def larguras_de_cartoes(total: int) -> list[int]:
    """Quantas colunas (de seis) cada cartão ocupa para as linhas ficarem sempre cheias:
    até três por linha e nunca uma linha com um cartão sozinho quando dá para repartir em
    duas — 4 cartões viram 2+2, e não 3+1."""
    restante, larguras = int(total or 0), []
    while restante > 0:
        por_linha = 2 if restante == 4 else min(3, restante)
        larguras += [6 // por_linha] * por_linha
        restante -= por_linha
    return larguras


CUSTEIO_CURTO = {"unidade": "Unidade", "outra_instituicao": "Outra instituição",
                 "onus_limitado": "Ônus limitado"}


@register.filter
def custeio_curto(custeio: str) -> str:
    """Só o nome do custeio. A explicação entre parênteses cabe na folha do ofício; num
    resumo, ela ocuparia três linhas para dizer "Unidade"."""
    return CUSTEIO_CURTO.get(custeio, custeio)


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
def so_avisos(pendencias):
    """Só as pendências que não impedem a emissão (agrupadas numa nota só na tela)."""
    return [p for p in pendencias if not p.bloqueia]


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


@register.filter
def uf_de(cidade: object) -> str:
    """"Curitiba/PR" → "PR" (a UF de um destino escrito como Cidade/UF); vazio se não houver."""
    texto = str(cidade or "")
    return texto.rsplit("/", 1)[1].strip().upper() if "/" in texto else ""


@register.inclusion_tag("viagens/_destinos.html", takes_context=True)
def campo_destinos(context, campo, unidade=None, maximo: int = 10, titulo: str = "") -> dict:
    """O componente de destinos de todas as telas que pedem destino (termo, OS, plano,
    evento do plano, viagem): a lista "Sede e destinos" do roteiro — a sede da unidade
    fixa no topo e na volta, uma linha por destino (UF + cidade), "Adicionar destino" — e o
    painel Rota ao lado (mapa, km e tempo). A sede só desenha a rota: não vai ao formulário.

    `campo` é um CampoMunicipios (cada destino vai como "Cidade/UF", na ordem da tela);
    `unidade`, a da folha (na falta, a de quem está usando)."""
    from django.conf import settings

    from gestao.cadastros.models import ConfiguracaoInstitucional
    from gestao.viagens import policies
    from gestao.viagens.forms import UFS

    if not unidade and "request" in context:
        unidade = policies.unidade_do_usuario(context["request"].user)
    config = (ConfiguracaoInstitucional.objects.filter(unidade=unidade)
              .select_related("sede").first() if unidade else None)
    sede = f"{config.sede.nome}/{config.sede.uf}" if config else ""
    valores = [str(v) for v in (campo.value() or []) if str(v).strip()]
    return {"campo": campo, "valores": valores, "sede": sede, "sede_uf": uf_de(sede),
            "ufs": UFS, "maximo": maximo, "titulo": titulo or "Sede e destinos",
            "mapa_tiles": settings.MAPA_TILES_URL, "mapa_atribuicao": settings.MAPA_ATRIBUICAO,
            "csp_nonce": context.get("csp_nonce", "")}
