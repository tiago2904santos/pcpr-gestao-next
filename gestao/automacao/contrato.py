"""Nomes do contrato v1 (API e eventos ao n8n) para o que é interno ao PCPR.

Os tipos de comunicação e os fluxos têm nomes nossos (`viagens.diarias_liberadas`,
`diarias_liberadas`); o contrato (`docs/automacao/contratos/`) usa um enum fechado de tipos e
fluxos em `[a-z0-9-]`. A tradução fica aqui, num lugar só, e um teste confere que todo tipo
registrado tem par no enum do esquema.
"""

from __future__ import annotations

#: Nossos tipos → `tipo_comunicacao` do contrato (enum fechado do esquema de eventos).
TIPOS_CONTRATO: dict[str, str] = {
    "viagens.diarias_liberadas": "mensagem_saque",
    "viagens.lembrete_comprovante": "lembrete_pendencia",
    "viagens.link_km": "link_km",
    "viagens.lembrete_km": "lembrete_pendencia",
    "viagens.aviso_cancelamento": "aviso_cancelamento",
    "viagens.aviso_reagendamento": "aviso_reagendamento",
    "viagens.aviso_substituicao": "aviso_substituicao",
    "viagens.aviso_retirada": "aviso_substituicao",
    "automacao.confirmacao": "resposta_recebimento",
    "automacao.arquivo_recusado": "resposta_recebimento",
    "automacao.encaminhada": "resposta_encaminhamento",
    "automacao.resposta": "resposta_encaminhamento",
    "automacao.ajuda": "resposta_assistente",
    "automacao.assistente": "resposta_assistente",
    "automacao.descadastro": "resposta_assistente",
    "automacao.boas_vindas": "resposta_assistente",
}


def tipo(chave: str) -> str:
    """O `tipo_comunicacao` do contrato; tipo sem par sai como resposta automática."""
    return TIPOS_CONTRATO.get(chave, "resposta_assistente")


def fluxo(nome: str | None) -> str | None:
    """`diarias_liberadas` → `diarias-liberadas` (o contrato só aceita `[a-z0-9-]`)."""
    return nome.replace("_", "-").replace(".", "-").lower()[:64] if nome else None
