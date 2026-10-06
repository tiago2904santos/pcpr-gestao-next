"""Escritas dos cadastros do Coffee Break (CB1). A trilha de auditoria é do banco."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import ProtectedError

from . import dominio, policies
from .models import ConfiguracaoOficio


class CadastroEmUso(Exception):
    pass


def _exigir(usuario) -> None:
    if not policies.pode_gerir_cadastros(usuario):
        raise PermissionDenied


@transaction.atomic
def salvar(usuario, form):
    """Grava o formulário já validado (o do lote também acerta os municípios)."""
    _exigir(usuario)
    obj = form.save(commit=False)
    if hasattr(obj, "razao_social"):
        obj.razao_social = " ".join(obj.razao_social.split())
    obj.save()
    form.save_m2m()
    if hasattr(form, "municipios_resolvidos"):
        obj.municipios.set(form.municipios_resolvidos)
        obj.municipios_texto = form.cleaned_data.get("lista_municipios", "")
        obj.save(update_fields=["municipios_texto", "atualizado_em"])
    return obj


@transaction.atomic
def excluir(usuario, obj, singular: str) -> None:
    """Excluir o que está em uso é recusado (as chaves protegem)."""
    _exigir(usuario)
    arquivo = getattr(obj, "arquivo", None)
    try:
        with transaction.atomic():
            obj.delete()
    except ProtectedError:
        raise CadastroEmUso(dominio.MSG_EM_USO.format(singular=singular)) from None
    if arquivo:
        transaction.on_commit(lambda: arquivo.delete(save=False))


def configuracao() -> ConfiguracaoOficio:
    """O registro único (nasce com os valores neutros na primeira leitura)."""
    return ConfiguracaoOficio.atual()


@transaction.atomic
def salvar_configuracao(usuario, form) -> ConfiguracaoOficio:
    _exigir(usuario)
    return form.save()


def apagar_arquivo_depois(modelo, nome: str) -> None:
    """O PDF trocado sai do disco depois do commit, se nenhum outro registro aponta para ele."""
    if not nome or modelo.objects.filter(arquivo=nome).exists():
        return
    storage = modelo._meta.get_field("arquivo").storage
    transaction.on_commit(lambda: storage.delete(nome))
