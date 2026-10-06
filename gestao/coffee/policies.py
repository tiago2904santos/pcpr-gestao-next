"""Quem pode o quê no Coffee Break (paridade com `coffee_break/permissions.py`): quem tem o
módulo vê tudo (sem isolamento por setor ou autor); os cadastros contratuais são do
administrador do módulo (o módulo + o perfil ADMINISTRADOR)."""

from __future__ import annotations


def pode_acessar(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("coffee.acessar_coffee"))


MODELO_DA_TABELA = {"fornecedores": "fornecedor", "contratos": "contrato",
                    "aditivos": "termoaditivo", "lotes": "lote",
                    "configuracao": "configuracaooficio"}


def pode_gerir_cadastros(usuario, tabela: str = "") -> bool:
    """O administrador do módulo; por tabela, a permissão de alterar aquele cadastro."""
    modelo = MODELO_DA_TABELA.get(tabela, "fornecedor")
    return pode_acessar(usuario) and usuario.has_perm(f"coffee.change_{modelo}")
