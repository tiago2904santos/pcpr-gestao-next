"""Páginas do piloto verificadas em todos os testes de navegador.

`{oficio_emitido}` etc. são preenchidos com ids do cenário fictício.
"""

ROTAS_PUBLICAS = ["/conta/entrar/"]

ROTAS_AUTENTICADAS = [
    "/",
    "/viagens/",
    "/viagens/oficios/",
    "/viagens/oficios/?situacao=rascunho",
    "/viagens/oficios/?q=nada-encontrado-xyz",
    "/viagens/oficios/{oficio_rascunho}/editar/",
    "/viagens/oficios/{oficio_emitido}/",
    "/ui-lab/",
    "/nao-existe/",
]


def resolver(rota: str, ids: dict[str, int]) -> str:
    return rota.format(**ids)
