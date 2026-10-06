"""Preencher a pauta nova com um e-mail (P2; comportamento da referência,
`publicacoes/preenchimento.py` §2.5 — leitura própria em `dominio_email`): data e início da
pauta, título, unidade (só sugestão; sem cadastro, o nome vai para "Outra unidade"), fonte
e o jornalista responsável (quem está registrando, quando o nome casa com a equipe). Nada
aqui grava."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from gestao.plataforma.leitura_email import dobrar

from . import dominio_email, policies
from .models import Integrante, UnidadeResponsavel

MSG_VAZIO = ("Não deu para ler nada do texto: confira se é o release ou o pedido de "
             "divulgação (com o título e quem assina).")


@dataclass
class Sugestoes:
    iniciais: dict = field(default_factory=dict)
    lidos: list[tuple[str, str]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _integrante_de(usuario) -> Integrante | None:
    nome = dobrar(" ".join((getattr(usuario, "nome", "") or "").split()))
    if not nome:
        return None
    for i in Integrante.objects.all():
        if dobrar(" ".join(i.nome.split())) == nome:
            return i
    return None


def sugerir(usuario, texto: str) -> Sugestoes:
    if not policies.pode_criar(usuario):
        raise PermissionDenied
    agora = timezone.localtime().replace(tzinfo=None)
    unidades = list(UnidadeResponsavel.objects.values_list("pk", "nome"))
    leitura = dominio_email.ler(texto, agora, unidades)
    s = Sugestoes()
    if leitura.vazia:
        s.avisos.append(MSG_VAZIO)
        return s
    nomes = dict(unidades)
    jornalista = _integrante_de(usuario)
    campos = (
        ("data", "Data da pauta", leitura.data,
         f"{leitura.data:%d/%m/%Y}" if leitura.data else ""),
        ("inicio_pauta", "Início da pauta", leitura.inicio,
         f"{leitura.inicio:%H:%M}" if leitura.inicio else ""),
        ("titulo", "Título", leitura.titulo, leitura.titulo),
        ("unidade", "Unidade", leitura.unidade_id, nomes.get(leitura.unidade_id or 0, "")),
        ("unidade_nova", "Outra unidade (sugestão, confira)", leitura.unidade_texto,
         leitura.unidade_texto),
        ("fonte", "Fonte", leitura.fonte, leitura.fonte),
        ("jornalista", "Jornalista responsável", jornalista.pk if jornalista else None,
         jornalista.nome if jornalista else ""),
    )
    for chave, rotulo, valor, mostrado in campos:
        if valor not in ("", None):
            s.iniciais[chave] = valor
            s.lidos.append((rotulo, mostrado))
    return s
