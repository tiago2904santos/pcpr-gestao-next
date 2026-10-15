"""Modelos de OS (cadastro do gestor): criar, alterar, desativar e excluir.

Um modelo tem o texto de cada etapa da viagem e as funções da equipe (`ModeloOS`, `FuncaoOS`;
regras em `dominio.modelo_os`). Desativar tira o modelo das opções sem mexer nas OS que o
usam; excluir só sem OS ligada, e nunca um modelo do sistema. Toda gravação passa por aqui;
a auditoria é do banco (trigger).
"""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from . import policies
from .dominio import modelo_os as dominio
from .models import FuncaoOS, ModeloOS

MAX_FUNCOES = 6


class ModeloInvalido(Exception):
    """Erro com mensagem pronta para o usuário."""


def opcoes() -> list[ModeloOS]:
    """Os modelos que o cadastro da OS oferece: só os ativos, na ordem combinada."""
    return list(ModeloOS.objects.filter(ativo=True).prefetch_related("funcoes"))


def em_uso(modelo: ModeloOS) -> int:
    return modelo.ordens.count()


def codigos_em_uso(modelo: ModeloOS) -> set[str]:
    """As funções que alguma OS do modelo gravou (não podem sumir do modelo)."""
    usados: set[str] = set()
    for funcoes in modelo.ordens.values_list("funcoes", flat=True):
        usados.update(v for v in (funcoes or {}).values() if v)
    return usados


def _codigo(nome: str, usados: set[str]) -> str:
    base = (slugify(nome).replace("-", "_")[:28] or "funcao")
    codigo, n = base, 2
    while codigo in usados:
        codigo, n = f"{base}_{n}", n + 1
    return codigo


def validar_textos(textos: dict[str, str], funcoes: list[dict]) -> dict[str, str]:
    """{campo: mensagem} dos marcadores que o texto não pode usar (vazio = tudo certo)."""
    erros: dict[str, str] = {}
    for etapa in dominio.ETAPAS:
        ruins = dominio.marcadores_invalidos(textos.get(etapa, ""), dominio.MARCADORES_ETAPA)
        if ruins:
            erros[etapa] = "Marcador desconhecido: " + ", ".join(
                "{" + m + "}" for m in sorted(ruins))
    for i, f in enumerate(funcoes, 1):
        ruins = dominio.marcadores_invalidos(f.get("texto", ""), dominio.MARCADORES_FUNCAO)
        if ruins:
            erros[f"funcao_texto_{i}"] = "Marcador desconhecido aqui: " + ", ".join(
                "{" + m + "}" for m in sorted(ruins))
    return erros


@transaction.atomic
def salvar(usuario, *, pk: int | None = None, nome: str, referencia: str,
           textos: dict[str, str], justificativas: str = "", finalidade: str = "",
           funcoes: list[dict] | None = None) -> ModeloOS:
    """Cria (sem `pk`) ou altera um modelo. `funcoes`: [{"codigo", "nome", "icone", "texto"}]
    na ordem da tela; sem código é função nova (o código nasce do nome)."""
    policies.exigir(policies.pode_gerir_modelos_os(usuario),
                    "Você não pode criar nem alterar modelos de OS.")
    nome = " ".join((nome or "").split())[:60]
    referencia = " ".join((referencia or "").split())[:120]
    if not nome:
        raise ModeloInvalido("Dê um nome ao modelo, ex.: “Operação policial”.")
    if not referencia:
        raise ModeloInvalido("Informe a referência (o “Ref.:” do documento).")
    funcoes = [f for f in (funcoes or []) if (f.get("nome") or "").strip()]
    if len(funcoes) > MAX_FUNCOES:
        raise ModeloInvalido(f"No máximo {MAX_FUNCOES} funções por modelo.")
    for f in funcoes:
        if not (f.get("texto") or "").strip():
            raise ModeloInvalido(f"Escreva a atribuição da função “{f['nome']}”.")
    erros = validar_textos(textos, funcoes)
    if erros:
        raise ModeloInvalido(next(iter(erros.values())))
    duplicado = ModeloOS.objects.filter(nome__iexact=nome)
    if pk:
        duplicado = duplicado.exclude(pk=pk)
    if duplicado.exists():
        raise ModeloInvalido(f"Já existe um modelo chamado “{nome}”. Use outro nome.")
    modelo = ModeloOS.objects.select_for_update().get(pk=pk) if pk else ModeloOS()
    modelo.nome, modelo.referencia = nome, referencia
    for etapa in dominio.ETAPAS:
        setattr(modelo, etapa, (textos.get(etapa) or "").strip())
    modelo.justificativas = "\n".join(
        linha.strip() for linha in (justificativas or "").splitlines() if linha.strip())
    modelo.finalidade = (finalidade or "").strip()
    modelo.save()
    _gravar_funcoes(modelo, funcoes)
    return modelo


def _gravar_funcoes(modelo: ModeloOS, funcoes: list[dict]) -> None:
    atuais = {f.codigo: f for f in modelo.funcoes.all()}
    usados = codigos_em_uso(modelo)
    novos: set[str] = set()
    for ordem, f in enumerate(funcoes):
        codigo = (f.get("codigo") or "").strip()
        if codigo not in atuais:
            codigo = _codigo(f["nome"], set(atuais) | novos)
        if codigo in novos:
            raise ModeloInvalido(f"Duas funções com o mesmo código “{codigo}”.")
        novos.add(codigo)
        FuncaoOS.objects.update_or_create(
            modelo=modelo, codigo=codigo,
            defaults={"nome": " ".join(f["nome"].split())[:40],
                      "icone": (f.get("icone") or "")[:40], "texto": f["texto"].strip(),
                      "ordem": ordem})
    for codigo, funcao in atuais.items():
        if codigo not in novos:
            if codigo in usados:
                raise ModeloInvalido(f"A função “{funcao.nome}” está em uso em alguma OS deste "
                                     "modelo e não pode ser removida.")
            funcao.delete()


@transaction.atomic
def alternar_ativo(usuario, pk: int) -> ModeloOS:
    """Desativar tira o modelo das opções sem apagar (as OS que o usam continuam)."""
    policies.exigir(policies.pode_gerir_modelos_os(usuario),
                    "Você não pode ativar nem desativar modelos de OS.")
    modelo = ModeloOS.objects.select_for_update().get(pk=pk)
    modelo.ativo = not modelo.ativo
    modelo.save(update_fields=["ativo", "atualizado_em"])
    return modelo


@transaction.atomic
def excluir(usuario, pk: int) -> str:
    modelo = ModeloOS.objects.select_for_update().get(pk=pk)
    policies.exigir(policies.pode_excluir_modelo_os(usuario, modelo),
                    "Este modelo não pode ser excluído: desative-o para tirá-lo das opções.")
    if em_uso(modelo):
        raise ModeloInvalido(f"“{modelo.nome}” está em uso por {em_uso(modelo)} OS. Para "
                             "tirá-lo das opções, desative-o.")
    nome = modelo.nome
    modelo.delete()
    return nome
