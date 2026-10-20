"""`{% painel_ia "viagens.rt_rascunho" p.pk %}`: o cartão de sugestão de um uso numa tela de
negócio (RT, ofício, plano, viagem). Mostra o estado da última sugestão do registro, o
botão de pedir (com os campos livres opcionais do uso) e o link para a revisão. Quem não vê
o registro pela política do contexto não vê nada; desligado, diz como seguir sem ele.

Usos relacionados (`{% painel_ia "uso" pk "outro.uso" %}`) entram só como link para a tela de
pedido (que confere a permissão): as folhas têm orçamento de consultas, e cada cartão completo
custa algumas.
"""

from __future__ import annotations

from django import template

from gestao.plataforma import recursos

from .. import ganchos, policies, servicos
from ..models import ConfiguracaoUso, PedidoSugestao, Sugestao

register = template.Library()
CHAVE_CACHE = "assistencia:configuracoes"


def _configuracao(context, chave: str) -> ConfiguracaoUso:
    """Uma consulta por página para todas as configurações (render_context)."""
    cache = context.render_context.get(CHAVE_CACHE)
    if cache is None:
        cache = {c.uso: c for c in ConfiguracaoUso.objects.all()}
        context.render_context[CHAVE_CACHE] = cache
    return cache.get(chave) or ConfiguracaoUso(uso=chave)


@register.inclusion_tag("assistencia/_painel_uso.html", takes_context=True)
def painel_ia(context, chave: str, recurso_id, *relacionados: str) -> dict:
    if not recursos.ligado(recursos.IA):  # IA desligada (ADR 0050): o cartão não aparece
        return {"mostrar": False}
    request = context.get("request")
    usuario = getattr(request, "user", None)
    uso = ganchos.uso(chave)
    recurso_id = str(recurso_id)
    if uso is None or usuario is None or not policies.pode_ver(usuario, uso, recurso_id):
        return {"mostrar": False}
    config = _configuracao(context, uso.chave)
    pedido = (PedidoSugestao.objects.filter(uso=uso.chave, recurso_id=recurso_id)
              .select_related("sugestao__decidida_por").order_by("-id").first())
    sugestao = getattr(pedido, "sugestao", None) if pedido else None
    obsoleta = bool(sugestao and servicos.obsoleta(sugestao))
    outros = [u for u in (ganchos.uso(r) for r in relacionados) if u is not None]
    return {
        "mostrar": True, "uso": uso, "recurso_id": recurso_id, "config": config,
        "pedido": pedido, "sugestao": sugestao, "obsoleta": obsoleta,
        "pendente": bool(pedido and pedido.estado in (PedidoSugestao.Estado.PENDENTE,
                                                      PedidoSugestao.Estado.PROCESSANDO)),
        "pronta": bool(sugestao and sugestao.estado == Sugestao.Estado.PRONTA and not obsoleta),
        "pode_pedir": config.ligado and policies.pode_pedir(usuario, uso, recurso_id),
        "relacionados": outros,
        "voltar": request.get_full_path() if request else "",
        "csrf_token": context.get("csrf_token"),
        "ident": f"ia-{uso.chave.replace('.', '-')}-{recurso_id}",
    }


@register.inclusion_tag("assistencia/_link_uso.html", takes_context=True)
def link_ia(context, chave: str, recurso_id) -> dict:
    """Entrada leve (nenhuma consulta) para listas e telas com orçamento de consultas: um link
    para a tela do pedido, que confere a permissão e mostra a última sugestão do registro."""
    uso = ganchos.uso(chave) if recursos.ligado(recursos.IA) else None
    request = context.get("request")
    return {"uso": uso, "recurso_id": str(recurso_id),
            "voltar": request.get_full_path() if request else ""}
