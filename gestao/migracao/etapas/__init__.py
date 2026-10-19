"""Etapas da migração, NA ORDEM (cada uma usa o mapa das anteriores).

Cada módulo expõe `executar(ctx: Contexto) -> None`. Uma etapa nunca apaga nada no destino e,
rodada de novo, só cria o que ainda não tem correspondência em `MapaLegado`.
"""

ORDEM = (
    "cadastros",      # municípios (mapa), unidades, cargos, servidores, viaturas, usuários…
    "viagens",        # viagens, roteiros, ofícios, termos, OS, planos, documentos e arquivos
    "prestacao",      # prestações, diários, RT, anexos, carimbos
    "eventos",        # solicitações de eventos, catálogos, notificações
    "coffee",         # coffee break
)
