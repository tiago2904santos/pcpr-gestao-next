"""Fontes de Viagens na busca global (paleta de comandos): ofícios (número 131/2026,
protocolo, motivo, destino ou servidor — a mesma busca da lista) e viagens (título ou
motivo). Só o que a pessoa vê pelas telas (policies)."""

from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from gestao.plataforma.busca import Fonte, Resultado, registrar_fonte

from . import policies
from .enderecos import url_na_lista
from .services import buscar_por_texto


def _oficios(usuario, termo: str, limite: int) -> list[Resultado]:
    qs = buscar_por_texto(policies.oficios_visiveis(usuario), termo)
    saida = []
    for o in qs.select_related("unidade").order_by("-ano", "-numero")[:limite]:
        # Emitido ou cancelado não tem folha para abrir: a busca leva à lista filtrada
        # nele, onde a janela de resumo mostra tudo.
        url = (reverse("viagens:editar", args=[o.pk]) if o.editavel
               else url_na_lista(o))
        saida.append(Resultado(f"Ofício {o.numero_formatado}", url,
                               f"{o.get_situacao_display()} · {o.motivo[:60]}", "file-text"))
    return saida


def _viagens(usuario, termo: str, limite: int) -> list[Resultado]:
    qs = (policies.viagens_visiveis(usuario)
          .filter(Q(titulo__unaccent__icontains=termo) | Q(motivo__unaccent__icontains=termo))
          .order_by("-data_inicio", "-pk")[:limite])
    return [Resultado(v.titulo or f"Viagem #{v.pk}",
                      reverse("viagens:editar_viagem", args=[v.pk]),
                      " · ".join(p for p in (v.get_situacao_display(),
                                             f"{v.data_inicio:%d/%m/%Y}" if v.data_inicio else "",
                                             (v.motivo or "")[:50]) if p), "map")
            for v in qs]


def _ve_viagens(usuario) -> bool:
    return bool(getattr(usuario, "is_authenticated", False)
                and usuario.has_perm("viagens.view_viagem"))


def registrar() -> None:
    registrar_fonte(Fonte("oficios", "Ofícios", policies.pode_listar, _oficios, ordem=10))
    registrar_fonte(Fonte("viagens", "Viagens", _ve_viagens, _viagens, ordem=11))
