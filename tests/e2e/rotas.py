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
    "/viagens/justificativas/",
    "/viagens/justificativas/?editar={oficio_rascunho}",  # janela de escrever aberta
    "/viagens/oficios/?situacao=arquivado",
    "/cadastros/textos-prontos/",
    "/cadastros/textos-prontos/?tipo=justificativa&novo=1",  # janela de novo texto aberta
    # Módulo 2 — cadastros em tela (o operador mantém; diárias e configuração ele só vê).
    "/cadastros/",
    "/cadastros/servidores/",
    "/cadastros/servidores/?novo=1",
    "/cadastros/servidores/?aba=incompletos",
    "/cadastros/viaturas/",
    "/cadastros/viaturas/?novo=1",
    "/cadastros/unidades/?novo=1",
    "/cadastros/cargos/",
    "/cadastros/combustiveis/?aba=inativos",
    "/cadastros/diarias/",
    "/cadastros/configuracao/",
    # Módulo 6a — catálogos do plano de trabalho.
    "/cadastros/atividades/",
    "/cadastros/conjuntos/?novo=1",  # janela com as caixas de escolha
    "/cadastros/horarios/?novo=1",
    # Módulo 4 — termos de autorização.
    "/viagens/termos/",
    "/viagens/termos/novo/?oficio={oficio_emitido}",
    # Módulo 5 — ordens de serviço.
    "/viagens/ordens/",
    "/viagens/ordens/nova/?oficio={oficio_emitido}",
    # Módulo 6 — planos de trabalho.
    "/viagens/planos/",
    "/viagens/planos/novo/?oficio={oficio_emitido}",
    "/ui-lab/",
    "/nao-existe/",
]


def resolver(rota: str, ids: dict[str, int]) -> str:
    return rota.format(**ids)
