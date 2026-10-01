"""Papéis (perfis) e suas permissões — fonte única.

Um papel é um `Group` do Django. A migração de dados e o comando
`sincronizar_papeis` criam/atualizam os grupos a partir deste dicionário, de
modo que a matriz de permissões fica versionada em Git e testada.
Ver docs/product/permissions.md.
"""

from __future__ import annotations

PAPEIS: dict[str, dict[str, object]] = {
    "OPERADOR_VIAGENS": {
        "descricao": "Monta ofícios, roteiros e termos da sua unidade.",
        "permissoes": [
            "viagens.view_oficio", "viagens.add_oficio", "viagens.change_oficio",
            "viagens.emitir_oficio",
            "cadastros.view_servidor", "cadastros.view_viatura", "cadastros.view_unidade",
        ],
    },
    "GESTOR_VIAGENS": {
        "descricao": "Tudo do operador + cancelar ofícios, reabrir emitidos, numeração e tabelas.",
        "permissoes": [
            "viagens.view_oficio", "viagens.add_oficio", "viagens.change_oficio",
            "viagens.emitir_oficio", "viagens.cancelar_oficio", "viagens.reabrir_oficio",
            "viagens.ver_todas_unidades", "viagens.gerir_numeracao",
            "cadastros.view_servidor", "cadastros.add_servidor", "cadastros.change_servidor",
            "cadastros.view_viatura", "cadastros.add_viatura", "cadastros.change_viatura",
            "cadastros.view_unidade", "cadastros.add_unidade", "cadastros.change_unidade",
            "cadastros.view_tabeladiaria", "cadastros.add_tabeladiaria",
        ],
    },
    "CONSULTA": {
        "descricao": "Somente leitura de ofícios e cadastros.",
        "permissoes": [
            "viagens.view_oficio", "viagens.ver_todas_unidades",
            "cadastros.view_servidor", "cadastros.view_viatura", "cadastros.view_unidade",
        ],
    },
    "ADMINISTRADOR": {
        "descricao": "Gestão de usuários, papéis e configurações institucionais.",
        "permissoes": [
            "identidade.view_usuario", "identidade.add_usuario", "identidade.change_usuario",
            "plataforma.view_eventoauditoria",
        ],
    },
}
