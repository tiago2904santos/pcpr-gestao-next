"""Autorização de Eventos Sociais (fonte única; views e menus usam estas funções).

Como na referência (docs/migration/eventos-sociais.md):

- todo usuário autenticado pode pedir um evento (o "solicitante" é todo mundo);
- vê a solicitação quem é o responsável por ela, a Diretoria-Geral e quem administra
  (`ver_todas_solicitacoes`); os demais só veem as próprias;
- só a Diretoria-Geral despacha (`despachar_solicitacao`; quem administra, não);
- os catálogos ficam com quem administra; os textos prontos do despacho também com a DG.

Matriz em docs/product/permissions.md.
"""

from __future__ import annotations

from django.db.models import QuerySet

MODELOS = {"tipos-evento": "tipoevento", "servicos": "servico", "equipes": "equipe",
           "orgaos": "orgaoresponsavel", "unidades-moveis": "unidademovel",
           "textos-despacho": "textodespacho"}


def _autenticado(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False))


def pode_gerir_catalogo(usuario, slug: str) -> bool:
    modelo = MODELOS.get(slug)
    return bool(modelo) and _autenticado(usuario) and usuario.has_perm(f"eventos.change_{modelo}")


def catalogos_visiveis(usuario) -> list[str]:
    return [slug for slug in MODELOS if pode_gerir_catalogo(usuario, slug)]


# ---------------------------------------------------------------- solicitações
def ve_todas(usuario) -> bool:
    return _autenticado(usuario) and usuario.has_perm("eventos.ver_todas_solicitacoes")


def pode_despachar(usuario) -> bool:
    return _autenticado(usuario) and usuario.has_perm("eventos.despachar_solicitacao")


def solicitacoes_visiveis(usuario) -> QuerySet:
    from .models import Solicitacao

    if not _autenticado(usuario):
        return Solicitacao.objects.none()
    qs = Solicitacao.objects.all()
    return qs if ve_todas(usuario) else qs.filter(criado_por=usuario)


def pode_ver(usuario, s) -> bool:
    return _autenticado(usuario) and (s.criado_por_id == usuario.pk or ve_todas(usuario))


def pode_criar(usuario) -> bool:
    return _autenticado(usuario)


def _responsavel(usuario, s) -> bool:
    return _autenticado(usuario) and (s.criado_por_id == usuario.pk or usuario.is_superuser)


def pode_editar_dados(usuario, s) -> bool:
    """Rascunho ou devolvida, pelo responsável."""
    return _responsavel(usuario, s) and s.status in ("rascunho", "devolvida")


def pode_reabrir(usuario, s) -> bool:
    """Alterar depois do envio (volta ao despacho), pelo responsável."""
    return _responsavel(usuario, s) and s.status in ("aguardando_despacho", "deferida")


def pode_concluir(usuario, s) -> bool:
    return _responsavel(usuario, s) and s.status == "deferida"


def pode_cancelar(usuario, s) -> bool:
    return (pode_ver(usuario, s) and s.status in ("aguardando_despacho", "devolvida", "deferida")
            and (_responsavel(usuario, s) or pode_despachar(usuario) or ve_todas(usuario)))


def pode_transferir(usuario, s) -> bool:
    return pode_ver(usuario, s) and not s.finalizada


def pode_excluir(usuario, s) -> bool:
    return _responsavel(usuario, s) and s.status == "rascunho"


def pode_mexer_nos_anexos(usuario, s) -> bool:
    return (pode_editar_dados(usuario, s) or pode_reabrir(usuario, s)) and not s.finalizada
