"""Escritas dos catálogos de Eventos Sociais (transação; autorização pelas policies).

Incluir, renomear (e o texto, no texto pronto do despacho), ativar/inativar e excluir — o
que está em uso não sai (o banco protege: "Use a ação Inativar…", como na referência).
E o modelo do tipo de evento (solicitante, cargo/unidade e órgão padrão, serviços
sugeridos, equipes com quantidade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from . import policies
from .models import (
    Equipe,
    OrgaoResponsavel,
    Servico,
    TextoDespacho,
    TipoEvento,
    TipoEventoEquipe,
    UnidadeMovel,
)

MSG_EM_USO = ("Este registro não pode ser excluído porque está vinculado a solicitações ou a "
              "outros cadastros. Use a ação Inativar para retirá-lo dos novos formulários.")


class CatalogoInvalido(ValueError):
    def __init__(self, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.campo = campo


@dataclass(frozen=True)
class Catalogo:
    slug: str
    titulo: str
    singular: str
    genitivo: str  # "do tipo de evento", "da equipe"
    modelo: Any
    icone: str
    com_texto: bool = False

    @property
    def url_name(self) -> str:
        return f"eventos:{self.slug}"


CATALOGOS: dict[str, Catalogo] = {c.slug: c for c in (
    Catalogo("tipos-evento", "Tipos de evento", "tipo de evento", "do tipo de evento",
             TipoEvento, "calendar-days"),
    Catalogo("servicos", "Serviços", "serviço", "do serviço", Servico, "list-checks"),
    Catalogo("equipes", "Equipes", "equipe", "da equipe", Equipe, "users"),
    Catalogo("orgaos", "Órgãos responsáveis", "órgão responsável", "do órgão responsável",
             OrgaoResponsavel, "landmark"),
    Catalogo("unidades-moveis", "Unidades móveis", "unidade móvel", "da unidade móvel",
             UnidadeMovel, "bus"),
    Catalogo("textos-despacho", "Textos prontos do despacho", "texto pronto",
             "do texto pronto", TextoDespacho, "text-quote", com_texto=True),
)}


def _exigir(usuario, slug: str) -> Catalogo:
    if slug not in CATALOGOS:
        raise PermissionDenied
    if not policies.pode_gerir_catalogo(usuario, slug):
        raise PermissionDenied
    return CATALOGOS[slug]


@transaction.atomic
def salvar(usuario, slug: str, dados: dict[str, Any], pk: int | None = None):
    cat = _exigir(usuario, slug)
    nome = " ".join((dados.get("nome") or "").split())
    if not nome:
        raise CatalogoInvalido("Informe o nome.", "nome")
    if len(nome) > 150:
        raise CatalogoInvalido("Use no máximo 150 caracteres.", "nome")
    modelo = cat.modelo
    if modelo.objects.filter(nome__iexact=nome).exclude(pk=pk or 0).exists():
        raise CatalogoInvalido(f"Já existe “{nome}” em {cat.titulo.lower()}.", "nome")
    registro = modelo.objects.select_for_update().get(pk=pk) if pk else modelo()
    registro.nome = nome
    if cat.com_texto:
        texto = (dados.get("texto") or "").strip()
        if not texto:
            raise CatalogoInvalido("Escreva o texto.", "texto")
        registro.texto = texto
    try:
        with transaction.atomic():
            registro.save()
    except IntegrityError as exc:
        raise CatalogoInvalido(f"Já existe “{nome}” em {cat.titulo.lower()}.", "nome") from exc
    return registro


@transaction.atomic
def alternar_ativo(usuario, slug: str, pk: int):
    cat = _exigir(usuario, slug)
    registro = cat.modelo.objects.select_for_update().get(pk=pk)
    registro.ativo = not registro.ativo
    registro.save(update_fields=["ativo", "atualizado_em"])
    return registro


@transaction.atomic
def excluir(usuario, slug: str, pk: int) -> str:
    cat = _exigir(usuario, slug)
    registro = cat.modelo.objects.select_for_update().get(pk=pk)
    nome = registro.nome
    try:
        with transaction.atomic():
            registro.delete()
    except ProtectedError as exc:
        raise CatalogoInvalido(MSG_EM_USO) from exc
    return nome


@transaction.atomic
def salvar_modelo(usuario, pk: int, *, solicitante: str, cargo: str,
                  orgao: OrgaoResponsavel | None, servicos: list[Servico],
                  equipes: dict[int, int | None]) -> TipoEvento:
    """O modelo da solicitação do tipo de evento. `equipes` = {equipe_id: quantidade}."""
    _exigir(usuario, "tipos-evento")
    tipo = TipoEvento.objects.select_for_update().get(pk=pk)
    tipo.solicitante_padrao = " ".join((solicitante or "").split())[:150]
    tipo.cargo_padrao = " ".join((cargo or "").split())[:255]
    tipo.orgao_padrao = orgao
    tipo.save()
    tipo.servicos_sugeridos.set(servicos)
    TipoEventoEquipe.objects.filter(tipo_evento=tipo).exclude(equipe_id__in=equipes).delete()
    for equipe_id, quantidade in equipes.items():
        TipoEventoEquipe.objects.update_or_create(tipo_evento=tipo, equipe_id=equipe_id,
                                                  defaults={"quantidade": quantidade})
    return tipo
