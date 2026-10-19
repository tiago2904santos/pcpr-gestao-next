"""A fila de exceções da automação (o que não se resolveu sozinho) na aba Pendências da
Agenda (`plataforma.pendencias`): as abertas que a pessoa vê (o recorte por unidade da
própria fila), as mais antigas primeiro."""

from __future__ import annotations

from datetime import date

from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.pendencias import Grupo, Item, Secao, carregar, registrar_secao

from . import policies
from .models import ExcecaoAutomacao


def _grupos(usuario, hoje: date) -> list[Grupo]:
    qs = (policies.filtrar_por_unidade(usuario, ExcecaoAutomacao.objects.filter(
        situacao=ExcecaoAutomacao.Situacao.ABERTA))
        .select_related("responsavel").order_by("criada_em", "pk"))
    linhas, total = carregar(qs)
    itens = []
    for e in linhas:
        fatos = [("alert-triangle", e.get_tipo_display()),
                 ("clock", f"Aberta em {timezone.localtime(e.criada_em):%d/%m/%Y}")]
        if e.responsavel_id:
            fatos.append(("user", f"Com {e.responsavel}"))
        itens.append(Item(chave=f"excecao-{e.pk}", titulo=e.resumo,
                          url=reverse("automacao:excecao", args=[e.pk]), acao="Tratar",
                          rotulo="Exceção", numero=f"#{e.pk}", fatos=tuple(fatos)))
    return [Grupo("excecoes", "Exceções abertas", total, itens,
                  ajuda="Assuma, trate e diga o que foi feito.",
                  ver_todos=reverse("automacao:excecoes"))]


def registrar() -> None:
    registrar_secao(Secao(
        "automacao", "Exceções da automação", "alert-triangle",
        "O que a automação não resolveu sozinha e espera uma pessoa.",
        policies.pode_ver, _grupos, vazio="Nenhuma exceção aberta.", ordem=60))
