"""Ofícios que um documento junta (o termo, a OS): têm de ser da mesma ação.

Um termo ou uma OS pode unir vários ofícios — as datas, os destinos e a equipe de todos —
desde que eles sejam condizentes: estejam na mesma viagem ou usem o mesmo roteiro. Ofícios
soltos, de ações diferentes, não se juntam (o documento sairia com dados de duas viagens).
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Oficio


def _comum(valores: set) -> object | None:
    """O valor que todos têm (None se diferem ou se algum não tem)."""
    return next(iter(valores)) if len(valores) == 1 and None not in valores else None


def incompatibilidade(oficios: Iterable[Oficio]) -> str:
    """A mensagem para a pessoa quando os ofícios não se juntam; vazio quando se juntam."""
    oficios = list(oficios)
    if len(oficios) < 2:
        return ""
    if _comum({o.roteiro_id for o in oficios}) or _comum({o.viagem_id for o in oficios}):
        return ""
    nomes = ", ".join(o.numero_formatado for o in oficios)
    return (f"Os ofícios {nomes} não são da mesma ação: para juntá-los, eles precisam estar "
            "na mesma viagem ou usar o mesmo roteiro.")


def compativeis(qs: QuerySet[Oficio], escolhidos: Iterable[Oficio]) -> QuerySet[Oficio]:
    """Os ofícios de `qs` que podem se juntar aos já escolhidos (a busca só oferece estes)."""
    escolhidos = list(escolhidos)
    if not escolhidos:
        return qs
    filtro = Q(pk__in=[])
    if (roteiro := _comum({o.roteiro_id for o in escolhidos})) is not None:
        filtro |= Q(roteiro_id=roteiro)
    if (viagem := _comum({o.viagem_id for o in escolhidos})) is not None:
        filtro |= Q(viagem_id=viagem)
    return qs.filter(filtro)


def resumo(oficio: Oficio) -> str:
    """A linha de baixo do cartão e da busca: situação · destinos · período (trechos
    carregados com o destino evitam uma consulta por ofício)."""
    trechos = list(oficio.trechos.all())
    destinos = list(dict.fromkeys(f"{t.destino.nome}/{t.destino.uf}" for t in trechos
                                  if t.destino_id != oficio.sede_id))
    periodo = ""
    if trechos:
        ida = timezone.localdate(trechos[0].saida_em)
        volta = timezone.localdate(trechos[-1].chegada_em)
        periodo = f"{ida:%d/%m/%Y}" if ida == volta else f"{ida:%d/%m} a {volta:%d/%m/%Y}"
    return " · ".join(p for p in (oficio.get_situacao_display(), ", ".join(destinos), periodo)
                      if p)
