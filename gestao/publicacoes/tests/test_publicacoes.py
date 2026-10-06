"""Publicações de ponta a ponta no servidor: acesso pelo papel, criar (unidade nova pelo
nome, unidade obrigatória), autosave, andamento (publicar sem data usa o agora) com
histórico, filas e filtros, CSV, painel (tempo médio), cadastros e a fonte da agenda."""

from __future__ import annotations

import csv
import io
from datetime import time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.identidade.models import Usuario
from gestao.plataforma import agenda
from gestao.publicacoes import historico, services
from gestao.publicacoes.models import Andamento, Integrante, Publicacao, UnidadeResponsavel

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


@pytest.fixture
def ascom():
    return _usuario("ascom", "ASCOM_PUBLICACOES")


@pytest.fixture
def cliente(ascom):
    c = Client()
    c.force_login(ascom)
    return c


@pytest.fixture
def gabi():
    return Integrante.objects.create(nome="Gabriela")


@pytest.fixture
def dp():
    return UnidadeResponsavel.objects.create(nome="DP de Irati")


def _dados(gabi, dp, **extra) -> dict:
    return {"data": timezone.localdate(), "inicio_pauta": time(9, 0), "jornalista": gabi,
            "unidade": dp, "titulo": "  Prisão em   flagrante ", "fonte": "Del. X", **extra}


def _post(gabi, dp, **extra) -> dict:
    hoje = timezone.localdate()
    base = {"data": f"{hoje:%d/%m/%Y}", "inicio_pauta": "9h", "jornalista": gabi.pk,
            "unidade": dp.pk if dp else "", "unidade_nova": "", "fonte": "Del. X",
            "titulo": "Prisão em flagrante", "colocada_edicao": "", "data_publicacao": "",
            "horario_publicacao": "", "revisao": "", "galeria_fotos": "", "bitly_grupos": "",
            "enviado_sesp": "", "publicado_aen": "", "link_site": "", "link_aen": ""}
    base.update(extra)
    return base


def test_acesso_pelo_papel(ascom):
    sem = _usuario("sem", "ASCOM_IMPRENSA")
    c = Client()
    c.force_login(sem)
    assert c.get(reverse("publicacoes:painel")).status_code == 403
    assert c.get(reverse("publicacoes:unidades")).status_code == 403
    with pytest.raises(PermissionDenied):
        services.criar(sem, {})


def test_criar_pela_tela_com_unidade_nova(cliente, gabi):
    UnidadeResponsavel.objects.create(nome="DHPP")
    r = cliente.post(reverse("publicacoes:nova"), _post(gabi, None, unidade_nova="dhpp",
                                                        titulo="  Título   da pauta "))
    p = Publicacao.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("publicacoes:pauta", args=[p.pk])
    assert p.unidade.nome == "DHPP" and UnidadeResponsavel.objects.count() == 1
    assert p.titulo == "Título da pauta" and p.inicio_pauta == time(9) and p.status == "pendente"


def test_unidade_obrigatoria_e_datas(cliente, gabi, dp):
    hoje = timezone.localdate()
    r = cliente.post(reverse("publicacoes:nova"), _post(gabi, None))
    assert "Escolha a unidade responsável ou informe uma nova." in r.content.decode()
    r = cliente.post(reverse("publicacoes:nova"), _post(
        gabi, dp, data_publicacao=f"{hoje - timedelta(days=1):%d/%m/%Y}"))
    assert "A publicação não pode ser anterior à data da pauta." in r.content.decode()
    assert not Publicacao.objects.exists()


def test_autosave_e_sim_nao(cliente, ascom, gabi, dp):
    p = services.criar(ascom, _dados(gabi, dp))
    url = reverse("publicacoes:autosave", args=[p.pk])
    r = cliente.post(url, _post(gabi, dp, enviado_sesp="1", publicado_aen="0",
                                link_site="https://example.invalid/x", colocada_edicao="10h"))
    assert r.json()["salvo"] is True
    p.refresh_from_db()
    assert (p.enviado_sesp, p.publicado_aen, p.bitly_grupos) == (True, False, None)
    assert p.colocada_edicao == time(10) and p.link_site == "https://example.invalid/x"
    r = cliente.post(url, _post(gabi, dp, link_site="não é link"))
    assert r.json()["salvo"] is False
    r = cliente.post(url, _post(gabi, None, unidade_nova="COPE"))
    assert r.json()["recarregar"] is True


def test_andamento_publica_com_o_agora_e_historico(cliente, ascom, gabi, dp):
    p = services.criar(ascom, _dados(gabi, dp))
    url = reverse("publicacoes:andamento", args=[p.pk])
    r = cliente.post(url, {"novo_status": "pendente", "anotacao": ""})
    assert r.status_code == 400 and "Escolha o novo status." in r.content.decode()
    cliente.post(url, {"novo_status": "em_andamento", "anotacao": "Redação"})
    r = cliente.post(url, {"novo_status": "publicada", "anotacao": "No ar"})
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.status == "publicada" and p.data_publicacao == timezone.localdate()
    assert p.horario_publicacao is not None and p.andamento == "No ar"
    assert Andamento.objects.count() == 2
    textos = [e.descricao for e in historico.da_pauta(p)]
    assert textos[0] == "Status: Publicada — No ar" and "Pauta registrada" in textos
    assert not any(t.startswith("Alterou") for t in textos)  # a publicação veio do andamento
    with pytest.raises(services.PautaInvalida, match="Informe a data em que"):
        services.salvar(ascom, p.pk, {"data_publicacao": None})


def test_lista_filas_filtros_csv(cliente, ascom, gabi, dp):
    outra = UnidadeResponsavel.objects.create(nome="DENARC")
    a = services.criar(ascom, _dados(gabi, dp, titulo="Furtos em série"))
    b = services.criar(ascom, _dados(gabi, outra, titulo="Apreensão de drogas"))
    services.registrar_andamento(ascom, b.pk, "publicada")
    lista = reverse("publicacoes:lista")
    html = cliente.get(lista).content.decode()
    assert "Furtos em série" in html and "Apreensão de drogas" in html
    assert 'Pendentes <span class="aba__contagem">1</span>' in html
    html = cliente.get(lista, {"fila": "publicadas"}).content.decode()
    assert "Apreensão" in html and "Furtos" not in html and "Publicada em" in html
    html = cliente.get(lista, {"q": "denarc"}).content.decode()
    assert "Apreensão" in html and "Furtos" not in html
    html = cliente.get(lista, {"unidade": dp.pk}).content.decode()
    assert "Furtos" in html and "Apreensão" not in html
    r = cliente.get(reverse("publicacoes:exportar"), {"fila": "publicadas"})
    linhas = list(csv.reader(io.StringIO(r.content.decode().lstrip("﻿")), delimiter=";"))
    assert linhas[0][-1] == "Tempo até publicar" and len(linhas) == 2
    assert linhas[1][5] == "Apreensão de drogas" and linhas[1][6] == "Publicada"
    assert a.pk != b.pk


def test_painel_vazio_e_tempo_medio(cliente, ascom, gabi, dp):
    html = cliente.get(reverse("publicacoes:painel")).content.decode()
    assert "Nada em aberto" in html and "Sem horários registrados no mês" in html
    hoje = timezone.localdate()
    p = services.criar(ascom, _dados(gabi, dp, inicio_pauta=time(9, 0),
                                     data_publicacao=hoje, horario_publicacao=time(10, 30)))
    services.registrar_andamento(ascom, p.pk, "publicada")
    html = cliente.get(reverse("publicacoes:painel")).content.decode()
    assert "1h30" in html and "100% das pautas" in html and "Gabriela" in html


def test_cadastros_do_administrador(gabi, ascom, dp):
    admin = _usuario("admin", "ADMINISTRADOR")
    c = Client()
    c.force_login(admin)
    url = reverse("publicacoes:unidades")
    assert c.post(url, {"nome": "DP de Castro"}).status_code == 302
    assert "Já existe" in c.post(url, {"nome": "dp de castro"}).content.decode()
    services.criar(ascom, _dados(gabi, dp))
    r = c.post(url, {"acao": "excluir", "pk": dp.pk})
    assert "não dá para excluir" in r.content.decode()
    html = c.get(reverse("publicacoes:equipe")).content.decode()
    assert "1 pauta" in html


def test_fonte_da_agenda(ascom, gabi, dp):
    hoje = timezone.localdate()
    p = services.criar(ascom, _dados(gabi, dp))
    c = services.criar(ascom, _dados(gabi, dp, titulo="Outra"))
    services.registrar_andamento(ascom, c.pk, "cancelada")
    itens = {i.chave: i for i in agenda.compromissos_de(ascom, hoje, hoje, ["pauta"])}
    assert itens[f"pauta-{p.pk}"].hora == "09:00" and not itens[f"pauta-{p.pk}"].prazo
    assert itens[f"pauta-{c.pk}"].encerrado


def test_duplicar_pauta_abre_a_nova_sem_a_publicacao(cliente, ascom, gabi, dp):
    p = services.criar(ascom, _dados(gabi, dp, link_site="https://example.invalid/x"))
    r = cliente.post(reverse("publicacoes:duplicar", args=[p.pk]))
    nova = Publicacao.objects.exclude(pk=p.pk).get()
    assert r["Location"] == reverse("publicacoes:pauta", args=[nova.pk])
    assert nova.titulo == p.titulo and nova.jornalista == gabi and not nova.link_site
