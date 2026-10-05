"""Catálogos de Eventos Sociais: carga inicial, quem mantém (ADMINISTRADOR; textos do
despacho também a DG), incluir/renomear/inativar/excluir, nome repetido, em uso não sai,
e o modelo da solicitação do tipo de evento."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from gestao.eventos import catalogos
from gestao.eventos.models import Equipe, OrgaoResponsavel, Servico, TextoDespacho, TipoEvento
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


def test_carga_inicial():
    assert TipoEvento.objects.filter(nome="PCPR na Comunidade").exists()
    assert Servico.objects.filter(nome="Emissão de CIN").exists()
    assert OrgaoResponsavel.objects.count() >= 3 and Equipe.objects.count() >= 3


def test_quem_mantem():
    admin = _usuario("admin", "ADMINISTRADOR")
    dg = _usuario("dg", "GESTOR_DG")
    op = _usuario("op", "OPERADOR_VIAGENS")
    c = Client()
    c.force_login(op)
    assert c.get(reverse("eventos:cadastros")).status_code == 403
    c.force_login(dg)
    assert c.get(reverse("eventos:textos-despacho")).status_code == 200
    assert c.get(reverse("eventos:servicos")).status_code == 403
    with pytest.raises(PermissionDenied):
        catalogos.salvar(dg, "servicos", {"nome": "X"})
    c.force_login(admin)
    html = c.get(reverse("eventos:cadastros")).content.decode()
    assert "Unidades móveis" in html and "Textos prontos do despacho" in html


def test_incluir_renomear_inativar_excluir():
    admin = _usuario("admin", "ADMINISTRADOR")
    c = Client()
    c.force_login(admin)
    url = reverse("eventos:unidades-moveis")
    assert c.post(url, {"nome": "  Caminhão   1 "}).status_code == 302
    u = catalogos.CATALOGOS["unidades-moveis"].modelo.objects.get()
    assert u.nome == "Caminhão 1"
    assert "Já existe" in c.post(url, {"nome": "caminhão 1"}).content.decode()
    c.post(url, {"pk": u.pk, "nome": "Caminhão 01"})
    c.post(url, {"pk": u.pk, "acao": "ativo"})
    u.refresh_from_db()
    assert u.nome == "Caminhão 01" and not u.ativo
    assert "Inativo" in c.get(url, {"situacao": "inativos"}).content.decode()
    c.post(url, {"pk": u.pk, "acao": "excluir"})
    assert not type(u).objects.exists()
    texto = reverse("eventos:textos-despacho")
    assert "Escreva o texto." in c.post(texto, {"nome": "Deferir", "texto": ""}).content.decode()
    c.post(texto, {"nome": "Deferir", "texto": "Defiro, nos termos."})
    assert TextoDespacho.objects.get().texto == "Defiro, nos termos."


def test_modelo_do_tipo():
    admin = _usuario("admin", "ADMINISTRADOR")
    c = Client()
    c.force_login(admin)
    tipo = TipoEvento.objects.get(nome="Palestra")
    orgao = OrgaoResponsavel.objects.first()
    servico = Servico.objects.get(nome="Emissão de CIN")
    alfa = Equipe.objects.get(nome="Alfa")
    url = reverse("eventos:modelo_do_tipo", args=[tipo.pk])
    r = c.post(url, {"solicitante": "Escola", "cargo": "Direção", "orgao": orgao.pk,
                     "servicos": [servico.pk], f"equipe_{alfa.pk}": "1",
                     f"quantidade_{alfa.pk}": "zero"})
    assert "Informe uma quantidade válida para Alfa." in r.content.decode()
    r = c.post(url, {"solicitante": "Escola", "cargo": "Direção", "orgao": orgao.pk,
                     "servicos": [servico.pk], f"equipe_{alfa.pk}": "1",
                     f"quantidade_{alfa.pk}": "3"})
    assert r.status_code == 302
    tipo.refresh_from_db()
    assert tipo.tem_modelo and tipo.orgao_padrao == orgao
    assert list(tipo.servicos_sugeridos.all()) == [servico]
    assert tipo.equipes_padrao.get().quantidade == 3
    # Órgão padrão do modelo não impede excluir (o tipo fica sem órgão); o que as
    # solicitações usam (PROTECT, fatia E2) é recusado com "Use a ação Inativar…".
    catalogos.excluir(admin, "orgaos", orgao.pk)
    tipo.refresh_from_db()
    assert tipo.orgao_padrao is None
