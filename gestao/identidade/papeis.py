"""Papéis (perfis) e suas permissões — fonte única.

Um papel é um `Group` do Django. A função `sincronizar_papeis`, chamada no
`post_migrate`, cria/atualiza os grupos a partir deste dicionário, de
modo que a matriz de permissões fica versionada em Git e testada.
Ver docs/product/permissions.md.
"""

from __future__ import annotations

from typing import TypedDict


class Papel(TypedDict):
    descricao: str
    permissoes: list[str]


# Como na referência, a equipe de viagens (gestor e operador) mantém os cadastros de apoio;
# a tabela de diárias (dinheiro) e a configuração da unidade são só do gestor.
CADASTROS_DA_EQUIPE = [
    f"cadastros.{acao}_{modelo}"
    for modelo in ("servidor", "viatura", "unidade", "cargo", "combustivel",
                   "programasolicitante", "horarioatendimento", "atividadeplano",
                   "presetatividades", "tipoviagem")
    for acao in ("view", "add", "change", "delete")
]

PAPEIS: dict[str, Papel] = {
    "OPERADOR_VIAGENS": {
        "descricao": "Monta ofícios, roteiros, termos, ordens e planos da sua unidade.",
        "permissoes": [
            "viagens.view_oficio", "viagens.add_oficio", "viagens.change_oficio",
            "viagens.emitir_oficio", "viagens.delete_oficio", "viagens.arquivar_oficio",
            "viagens.view_roteiro", "viagens.add_roteiro", "viagens.change_roteiro",
            "viagens.delete_roteiro",
            "viagens.view_termoautorizacao", "viagens.add_termoautorizacao",
            "viagens.change_termoautorizacao", "viagens.delete_termoautorizacao",
            "viagens.view_ordemservico", "viagens.add_ordemservico",
            "viagens.change_ordemservico", "viagens.delete_ordemservico",
            "viagens.view_planotrabalho", "viagens.add_planotrabalho",
            "viagens.change_planotrabalho", "viagens.delete_planotrabalho",
            "viagens.view_viagem", "viagens.add_viagem", "viagens.change_viagem",
            "viagens.delete_viagem",
            "viagens.view_prestacaoservidor", "viagens.change_prestacaoservidor",
            *CADASTROS_DA_EQUIPE,
            "cadastros.view_tabeladiaria", "cadastros.view_configuracaoinstitucional",
            "cadastros.view_modelotexto", "cadastros.add_modelotexto",
            "cadastros.change_modelotexto",
        ],
    },
    "GESTOR_VIAGENS": {
        "descricao": "Tudo do operador + cancelar ofícios, reabrir emitidos, numeração e tabelas.",
        "permissoes": [
            "viagens.view_oficio", "viagens.add_oficio", "viagens.change_oficio",
            "viagens.emitir_oficio", "viagens.cancelar_oficio", "viagens.reabrir_oficio",
            "viagens.reativar_oficio", "viagens.arquivar_oficio",
            "viagens.delete_oficio", "cadastros.view_modelotexto", "cadastros.add_modelotexto",
            "cadastros.change_modelotexto", "cadastros.delete_modelotexto",
            "cadastros.gerir_padrao_texto",
            "viagens.view_roteiro", "viagens.add_roteiro", "viagens.change_roteiro",
            "viagens.delete_roteiro",
            "viagens.ver_todas_unidades", "viagens.gerir_numeracao",
            "viagens.view_termoautorizacao", "viagens.add_termoautorizacao",
            "viagens.change_termoautorizacao", "viagens.delete_termoautorizacao",
            "viagens.view_ordemservico", "viagens.add_ordemservico",
            "viagens.change_ordemservico", "viagens.delete_ordemservico",
            "viagens.view_planotrabalho", "viagens.add_planotrabalho",
            "viagens.change_planotrabalho", "viagens.delete_planotrabalho",
            "viagens.view_viagem", "viagens.add_viagem", "viagens.change_viagem",
            "viagens.delete_viagem",
            "viagens.view_prestacaoservidor", "viagens.change_prestacaoservidor",
            *CADASTROS_DA_EQUIPE,
            "cadastros.view_tabeladiaria", "cadastros.add_tabeladiaria",
            "cadastros.change_tabeladiaria", "cadastros.delete_tabeladiaria",
            "cadastros.view_configuracaoinstitucional",
            "cadastros.change_configuracaoinstitucional",
        ],
    },
    "CONSULTA": {
        "descricao": "Somente leitura de ofícios, roteiros e cadastros.",
        "permissoes": [
            "viagens.view_oficio", "viagens.ver_todas_unidades", "viagens.view_roteiro",
            "viagens.view_termoautorizacao", "viagens.view_ordemservico",
            "viagens.view_planotrabalho", "viagens.view_viagem",
            "viagens.view_prestacaoservidor",
            "cadastros.view_servidor",
            "cadastros.view_viatura", "cadastros.view_unidade",
            "cadastros.view_cargo", "cadastros.view_combustivel",
        ],
    },
    # Decisão do agente — a confirmar (docs/migration/decisoes.md): na referência o acesso é
    # pelo módulo ASCOM_ATENDIMENTO_IMPRENSA; aqui vira um papel. Quem tem o papel vê e edita
    # todos os atendimentos e pode incluir um veículo novo pelo próprio atendimento.
    "ASCOM_IMPRENSA": {
        "descricao": "Atendimento à imprensa da ASCOM: registra pedidos, fontes, respostas e "
                     "andamentos.",
        "permissoes": [
            "imprensa.view_atendimento", "imprensa.add_atendimento",
            "imprensa.change_atendimento", "imprensa.view_integrante",
            "imprensa.view_veiculo", "imprensa.add_veiculo",
        ],
    },
    # Decisão do agente — a confirmar: na referência, o módulo ASCOM_PUBLICACOES.
    "ASCOM_PUBLICACOES": {
        "descricao": "Publicações da ASCOM: registra pautas, a edição, a publicação e a "
                     "divulgação.",
        "permissoes": [
            "publicacoes.view_publicacao", "publicacoes.add_publicacao",
            "publicacoes.change_publicacao", "publicacoes.view_integrante",
            "publicacoes.view_unidaderesponsavel", "publicacoes.add_unidaderesponsavel",
        ],
    },
    # Decisão do agente — a confirmar: na referência, o módulo ASCOM_DEMANDAS_EVENTOS, com a
    # palestra visível só aos setores de quem a registrou (aqui não há setores: vê todas).
    # Os cadastros de apoio (temas, palestrantes, respostas padrão) são do próprio módulo.
    # Coffee Break (referência: módulo ASCOM_COFFEE_BREAK) — quem tem o módulo vê tudo; os
    # cadastros são do administrador do módulo (este papel + ADMINISTRADOR).
    "ASCOM_COFFEE_BREAK": {
        "descricao": "Coffee Break da ASCOM: lotes, ordens de serviço e o fluxo de pagamento.",
        "permissoes": [
            "coffee.acessar_coffee",
            *(f"coffee.view_{modelo}" for modelo in (
                "fornecedor", "contrato", "termoaditivo", "lote", "configuracaooficio")),
        ],
    },
    "ASCOM_PALESTRAS": {
        "descricao": "Palestras e eventos da ASCOM: pedidos, agenda, palestrantes e respostas.",
        "permissoes": [
            "palestras.view_palestra", "palestras.add_palestra", "palestras.change_palestra",
            *(f"palestras.{acao}_{modelo}" for modelo in ("tema", "palestrante",
                                                          "respostapadrao")
              for acao in ("view", "add", "change", "delete")),
        ],
    },
    # Eventos Sociais (referência: grupo GESTOR_DG) — despacha as solicitações, vê todas e
    # mantém os textos prontos do despacho. (Pedir um evento é de todo usuário, sem papel.)
    "GESTOR_DG": {
        "descricao": "Diretoria-Geral: despacha as solicitações de evento social.",
        "permissoes": [
            "eventos.despachar_solicitacao", "eventos.ver_todas_solicitacoes",
            *(f"eventos.{acao}_textodespacho" for acao in ("view", "add", "change", "delete")),
        ],
    },
    "ADMINISTRADOR": {
        "descricao": "Gestão de usuários, papéis e configurações institucionais.",
        "permissoes": [
            "identidade.view_usuario", "identidade.add_usuario", "identidade.change_usuario",
            "plataforma.view_eventoauditoria",
            # Cadastros de apoio da imprensa (equipe e veículos), como na referência.
            *(f"imprensa.{acao}_{modelo}" for modelo in ("integrante", "veiculo")
              for acao in ("view", "add", "change", "delete")),
            # Os catálogos de Eventos Sociais e ver todas as solicitações (sem despachar),
            # como na referência.
            "eventos.ver_todas_solicitacoes",
            *(f"eventos.{acao}_{modelo}" for modelo in (
                "tipoevento", "servico", "equipe", "orgaoresponsavel", "unidademovel",
                "textodespacho", "tipoeventoequipe")
              for acao in ("view", "add", "change", "delete")),
            # E os de Publicações (equipe e unidades responsáveis).
            *(f"publicacoes.{acao}_{modelo}" for modelo in ("integrante", "unidaderesponsavel")
              for acao in ("view", "add", "change", "delete")),
            # Os cadastros contratuais do Coffee Break (com o papel do módulo, como na
            # referência: administrador do módulo = módulo + ADMINISTRADOR).
            *(f"coffee.{acao}_{modelo}" for modelo in (
                "fornecedor", "contrato", "termoaditivo", "lote", "configuracaooficio")
              for acao in ("view", "add", "change", "delete")),
        ],
    },
}


def sincronizar_papeis() -> dict[str, int]:
    """Cria/atualiza os grupos e suas permissões a partir de PAPEIS (idempotente)."""
    from django.contrib.auth.models import Group, Permission

    resultado = {}
    for nome, definicao in PAPEIS.items():
        grupo, _ = Group.objects.get_or_create(name=nome)
        perms = []
        for codigo in definicao["permissoes"]:
            app, codename = codigo.split(".")
            perm = Permission.objects.filter(content_type__app_label=app,
                                             codename=codename).first()
            if perm:
                perms.append(perm)
        grupo.permissions.set(perms)
        resultado[nome] = len(perms)
    return resultado
