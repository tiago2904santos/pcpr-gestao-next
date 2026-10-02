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
    # A leitura de um ofício é a janela de resumo, que abre na própria lista (ADR 0017);
    # `?resumo=` traz a janela desenhada no HTML e já aberta.
    "/viagens/oficios/?resumo={oficio_emitido}",
    "/viagens/roteiros/",
    "/viagens/roteiros/novo/",
    "/viagens/roteiros/{roteiro}/editar/",
    "/ui-lab/",
    "/nao-existe/",
]


def resolver(rota: str, ids: dict[str, int]) -> str:
    return rota.format(**ids)
