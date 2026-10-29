"""Uso de assistência dos Cadastros (descoberto pela assistência no `ready()` dela):

- AUT-86 `cadastros.atividade_complemento` — rascunho de meta e de recursos necessários de
  uma atividade/serviço do catálogo que está sem complemento. A meta não ganha número que o
  cadastro não tenha (o validador recusa): a quantidade é decisão do gestor. Aplicar grava
  pelo serviço do cadastro, sem sobrescrever o que já foi escrito sem confirmação.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse

from gestao.assistencia.dominio import textos as redacao
from gestao.assistencia.ganchos import (
    AplicacaoRecusada,
    Assunto,
    Contexto,
    Fato,
    Item,
    Obsoleta,
    RecursoInexistente,
    TextoHumano,
    UsoIA,
    registrar_uso,
)

from . import policies, services
from .models import AtividadePlano

CAMPOS = ("meta", "recurso")
ROTULOS = {"meta": "Meta", "recurso": "Recursos necessários"}
LACUNAS = {"quantidade": "Defina a quantidade da meta (ex.: atendimentos por dia): a "
                         "sugestão não inventa número."}


def _atividade(recurso_id: str) -> AtividadePlano:
    a = AtividadePlano.objects.filter(pk=int(recurso_id) if str(recurso_id).isdigit()
                                      else 0).first()
    if a is None:
        raise RecursoInexistente(recurso_id)
    return a


def _contexto(a: AtividadePlano) -> Contexto:
    fatos = tuple(f for f in (Fato("nome", "Catálogo · nome da atividade", a.nome),
                              Fato("codigo", "Catálogo · código", a.codigo)) if f.valor)
    return Contexto(recurso_rotulo=f"Atividade {a.nome}", fatos=fatos,
                    textos_atuais={"meta": a.meta, "recurso": a.recurso},
                    lacunas=("quantidade",))


def _montar(usuario, recurso_id: str, opcoes: dict) -> Contexto:
    if not policies.pode_ver_cadastro(usuario, AtividadePlano):
        raise RecursoInexistente(recurso_id)
    return _contexto(_atividade(recurso_id))


def _deterministico(ctx: Contexto) -> dict:
    nome = ctx.valor("nome")
    textos = []
    if not ctx.textos_atuais.get("meta", "").strip():
        textos.append({"campo": "meta", "fontes": ["nome"],
                       "texto": f"Realizar {nome[0].lower() + nome[1:]} para o público do "
                                "evento, conforme a demanda registrada no plano de trabalho."})
    if not ctx.textos_atuais.get("recurso", "").strip():
        textos.append({"campo": "recurso", "fontes": ["nome"],
                       "texto": f"Equipe capacitada e materiais necessários para {nome[0].lower()}"
                                f"{nome[1:]}."})
    return {"textos": textos, "lacunas": ["quantidade"]}


@transaction.atomic
def _aplicar(usuario, recurso_id: str, textos: dict[str, str], versao: str,
             substituir: bool) -> None:
    a = AtividadePlano.objects.select_for_update().get(pk=_atividade(recurso_id).pk)
    if _contexto(a).versao != versao:
        raise Obsoleta("A atividade mudou desde a sugestão.")
    for campo, texto in textos.items():
        atual = getattr(a, campo, "")
        if atual.strip() and not substituir and atual.strip() != texto.strip():
            raise TextoHumano("O campo já tem texto. Marque “Substituir o texto atual”.")
    try:
        services.salvar_atividade(usuario, pk=a.pk, nome=a.nome,
                                  meta=textos.get("meta", a.meta),
                                  recurso=textos.get("recurso", a.recurso))
    except (services.CadastroInvalido, PermissionDenied) as exc:
        raise AplicacaoRecusada(str(exc)) from exc


registrar_uso(UsoIA(
    chave="cadastros.atividade_complemento", codigo="AUT-86",
    rotulo="Meta e recursos de atividade do catálogo",
    descricao="Rascunho de meta e de recursos para atividades e serviços do catálogo que "
              "estão sem complemento. O gestor aprova; a quantidade da meta é dele.",
    versao_prompt="catalogo-v1",
    instrucoes=("Para a atividade do bloco de fatos, redija a `meta` (o que a atividade "
                "entrega, sem número) e os `recurso` necessários (pessoas e materiais, sem "
                "marcas nem valores), uma frase cada."),
    esquema=redacao.esquema_textos(CAMPOS, ("nome", "codigo"), LACUNAS, 400),
    campos_permitidos=("nome", "codigo"),
    dados_excluidos=("nomes de pessoas", "valores e preços", "fornecedores"),
    lacunas_conhecidas=LACUNAS, montar=_montar, deterministico=_deterministico,
    validar=lambda d, c: redacao.validar_textos(
        d, fatos_texto=redacao.serializar_fatos(c.fatos), chaves=("nome", "codigo"),
        campos_alvo=CAMPOS, max_caracteres=400),
    itens=lambda d, c: [Item(t["campo"], ROTULOS[t["campo"]], t["texto"],
                             tuple(c.rotulos(t["fontes"])), True,
                             "O campo já tem texto." if c.textos_atuais.get(t["campo"])
                             else "") for t in d.get("textos", [])],
    pode_pedir=lambda u, r: policies.pode_alterar_cadastro(u, AtividadePlano)
    and bool(_atividade(r)),
    pode_ver=lambda u, r: policies.pode_ver_cadastro(u, AtividadePlano) and bool(_atividade(r)),
    descrever=lambda r: Assunto(f"Atividade {_atividade(r).nome}",
                                reverse("cadastros:atividades") + f"?editar={int(r)}"),
    aplicar=_aplicar, versao_atual=lambda r: _contexto(_atividade(r)).versao,
    acao="Sugerir meta e recursos",
))
