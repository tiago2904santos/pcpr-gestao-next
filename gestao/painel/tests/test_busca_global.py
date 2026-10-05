"""Busca global (paleta de comandos): cada módulo entra com as suas fontes e só para quem
o vê; mínimo de 2 caracteres; resultados agrupados e com o link da folha."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.identidade.models import Usuario
from gestao.imprensa import services as imprensa
from gestao.palestras import services as palestras
from gestao.plataforma import busca
from gestao.publicacoes import services as publicacoes
from gestao.publicacoes.models import Integrante, UnidadeResponsavel

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


def test_fontes_por_papel_e_resultados_agrupados():
    ascom = _usuario("ascom", "ASCOM_IMPRENSA", "ASCOM_PUBLICACOES", "ASCOM_PALESTRAS")
    hoje = timezone.localdate()
    a = imprensa.criar(ascom, {"data": hoje, "jornalista": "Lúcia Xavante", "pedido": "Dados"})
    p = publicacoes.criar(ascom, {"data": hoje, "titulo": "Operação Xavante",
                                  "jornalista": Integrante.objects.create(nome="Gabi"),
                                  "unidade": UnidadeResponsavel.objects.create(nome="DP")})
    pal = palestras.criar(ascom, {"data_solicitacao": hoje, "solicitante": "Colégio Xavante"})
    c = Client()
    c.force_login(ascom)
    resultados = c.get(reverse("painel:busca"), {"q": "xavante"}).json()["resultados"]
    por_grupo = {r["grupo"]: r for r in resultados}
    assert por_grupo["Atendimentos à imprensa"]["url"] == reverse("imprensa:atendimento",
                                                                   args=[a.pk])
    assert por_grupo["Pautas"]["url"] == reverse("publicacoes:pauta", args=[p.pk])
    assert por_grupo["Palestras e eventos"]["url"] == reverse("palestras:palestra", args=[pal.pk])
    assert "Ofícios" not in por_grupo  # sem papel de Viagens, nem a fonte entra
    # Acentos não atrapalham: "lucia" acha "Lúcia".
    assert any(r["grupo"] == "Atendimentos à imprensa"
               for r in c.get(reverse("painel:busca"), {"q": "lucia"}).json()["resultados"])

    so_imprensa = _usuario("so", "ASCOM_IMPRENSA")
    assert [f.slug for f in busca.fontes_de(so_imprensa)] == ["imprensa"]
    assert busca.buscar(so_imprensa, "x") == []  # menos de 2 caracteres
    assert {r["grupo"] for r in busca.buscar(so_imprensa, "xavante")} == {
        "Atendimentos à imprensa"}


def test_viagens_entram_para_quem_ve_viagens():
    from gestao.viagens.tests.cenarios import cenario_completo

    c = cenario_completo()
    operador = c.usuarios["operador"]
    slugs = [f.slug for f in busca.fontes_de(operador)]
    assert "oficios" in slugs and "imprensa" not in slugs
