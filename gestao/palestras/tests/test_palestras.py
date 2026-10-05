"""Palestras de ponta a ponta no servidor: acesso pelo papel, criar (município Cidade/UF,
telefone/CEP/protocolo formatados, temas e palestrantes), autosave, andamento com o que o
status pede, resposta padrão com marcadores, lista e CSV, painel, cadastros e agenda."""

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

from gestao.cadastros.models import Municipio
from gestao.identidade.models import Usuario
from gestao.palestras import historico, services
from gestao.palestras.models import Palestra, Palestrante, RespostaEnviada, RespostaPadrao, Tema
from gestao.plataforma import agenda

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


@pytest.fixture
def ascom():
    return _usuario("ascom", "ASCOM_PALESTRAS")


@pytest.fixture
def cliente(ascom):
    c = Client()
    c.force_login(ascom)
    return c


@pytest.fixture
def curitiba():
    return Municipio.objects.get_or_create(codigo_ibge="4106902",
                                           defaults={"nome": "Curitiba", "uf": "PR"})[0]


def _post(**extra) -> dict:
    hoje = timezone.localdate()
    base = {"data_solicitacao": f"{hoje:%d/%m/%Y}", "canal_solicitacao": "email",
            "protocolo": "", "solicitante": "Colégio X", "telefone": "41999998888",
            "email": "Contato@Escola.invalid", "assunto_email": "", "pedido_contato": "",
            "informacoes_previas": "", "descricao": "", "evento": "palestra",
            "data_inicio_evento": "", "data_fim_evento": "", "hora_inicio": "",
            "municipio": "", "local": "", "endereco": "", "bairro": "", "cep": "",
            "quantidade_publico": ""}
    base.update(extra)
    return base


def test_acesso(ascom):
    sem = _usuario("sem", "ASCOM_IMPRENSA")
    c = Client()
    c.force_login(sem)
    assert c.get(reverse("palestras:painel")).status_code == 403
    assert c.get(reverse("palestras:buscar_palestrantes")).status_code == 403
    with pytest.raises(PermissionDenied):
        services.criar(sem, {})


def test_criar_com_formatos_temas_e_palestrantes(cliente, curitiba):
    tema = Tema.objects.create(nome="Golpes")
    ana = Palestrante.objects.create(nome="Ana", lotacao="DPCAP")
    r = cliente.post(reverse("palestras:nova"), {
        **_post(municipio="curitiba/pr", cep="80000000", canal_solicitacao="protocolo",
                protocolo="123456789"), "temas": [tema.pk], "palestrantes": [ana.pk]})
    p = Palestra.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("palestras:palestra", args=[p.pk])
    assert p.telefone == "(41) 99999-8888" and p.email == "contato@escola.invalid"
    assert p.cep == "80000-000" and p.protocolo == "12.345.678-9" and p.municipio == curitiba
    assert list(p.temas.all()) == [tema] and list(p.palestrantes.all()) == [ana]


def test_erros_do_formulario(cliente):
    r = cliente.post(reverse("palestras:nova"), _post(
        solicitante="", telefone="123", canal_solicitacao="protocolo",
        data_fim_evento="01/01/2026", municipio="Nenhures/XX"))
    html = r.content.decode()
    assert r.status_code == 200 and not Palestra.objects.exists()
    for msg in ("Informe o telefone com DDD", "Informe o número do protocolo",
                "Informe a data inicial do evento", "Não encontramos"):
        assert msg in html


def test_autosave_e_historico(cliente, ascom):
    p = services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "X"})
    url = reverse("palestras:autosave", args=[p.pk])
    r = cliente.post(url, _post(solicitante="X", local="Auditório", quantidade_publico="80"))
    assert r.json()["salvo"] is True
    p.refresh_from_db()
    assert p.local == "Auditório" and p.quantidade_publico == 80
    r = cliente.post(url, _post(cep="1"))
    assert r.json()["salvo"] is False and "CEP" in r.json()["mensagem"]
    textos = [e.descricao for e in historico.da_palestra(p)]
    assert "Pedido registrado" in textos and any(t.startswith("Alterou") for t in textos)


def test_andamento_completa_o_que_o_status_pede(cliente, ascom):
    p = services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "X"})
    ana = Palestrante.objects.create(nome="Ana")
    url = reverse("palestras:andamento", args=[p.pk])
    r = cliente.post(url, {"novo_status": "agendada"})
    html = r.content.decode()
    assert r.status_code == 400 and "Informe a data do evento." in html
    assert "Informe o palestrante." in html
    amanha = timezone.localdate() + timedelta(days=1)
    r = cliente.post(url, {"novo_status": "agendada", "data_evento": f"{amanha:%d/%m/%Y}",
                           "palestrante": ana.pk, "anotacao": "Confirmado"})
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.status == "agendada" and p.data_inicio_evento == amanha
    assert list(p.palestrantes.all()) == [ana] and p.andamento == "Confirmado"
    folha = cliente.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert 'value="atendida"' not in folha  # o evento ainda não aconteceu
    with pytest.raises(services.PalestraInvalida, match="depois da data do evento"):
        services.registrar_andamento(ascom, p.pk, "atendida", quantidade_publico=10)


def test_resposta_padrao(cliente, ascom, curitiba):
    p = services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "Escola X",
                               "data_inicio_evento": timezone.localdate(),
                               "hora_inicio": time(14), "municipio": curitiba,
                               "telefone": "41999998888", "email": "x@y.invalid"})
    resposta = RespostaPadrao.objects.create(
        tipo="Confirmação", mensagem="Olá, {solicitante}! Dia {data} às {horario} em {municipio}.")
    folha = cliente.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    hoje = timezone.localdate()
    assert f"Olá, Escola X! Dia {hoje:%d/%m/%Y} às 14:00 em Curitiba/PR." in folha
    r = cliente.post(reverse("palestras:responder", args=[p.pk]), {
        "resposta": resposta.pk, "texto": "", "novo_status": ""})
    assert r.status_code == 400
    r = cliente.post(reverse("palestras:responder", args=[p.pk]), {
        "resposta": resposta.pk, "texto": "Texto final", "novo_status": "em_andamento"})
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.status == "em_andamento" and RespostaEnviada.objects.get().texto == "Texto final"
    folha = cliente.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert "mailto:x@y.invalid" in folha and "https://wa.me/5541999998888" in folha
    assert "Resposta enviada: Confirmação" in folha


def test_lista_csv_e_painel(cliente, ascom, curitiba):
    golpes = Tema.objects.create(nome="Golpes")
    a = services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "Escola A",
                               "municipio": curitiba, "temas": [golpes]})
    services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "Empresa B",
                           "evento": "evento"})
    lista = reverse("palestras:lista")
    html = cliente.get(lista).content.decode()
    assert "Palestra · Curitiba" in html and 'Pendente <span class="aba__contagem">2</span>' in html
    html = cliente.get(lista, {"q": "golpes"}).content.decode()
    assert "Escola A" in html and "Empresa B" not in html
    html = cliente.get(lista, {"evento": "evento"}).content.decode()
    assert "Empresa B" in html and "Escola A" not in html
    r = cliente.get(reverse("palestras:exportar"), {"tema": golpes.pk})
    linhas = list(csv.reader(io.StringIO(r.content.decode().lstrip("﻿")), delimiter=";"))
    assert linhas[0][:3] == ["MÊS", "MUNICIPIO", "DATA DO EVENTO E HORA (PERÍODO)"]
    assert len(linhas) == 2 and linhas[1][7] == "Escola A" and linhas[1][2] == "À definir"
    html = cliente.get(reverse("palestras:painel")).content.decode()
    assert "Em aberto" in html and "Golpes" in html
    assert a.pk


def test_cadastros(cliente, ascom):
    url = reverse("palestras:temas")
    assert cliente.post(url, {"nome": "Golpes"}).status_code == 302
    assert "Já existe" in cliente.post(url, {"nome": "golpes"}).content.decode()
    tema = Tema.objects.get()
    services.criar(ascom, {"data_solicitacao": timezone.localdate(), "solicitante": "X",
                           "temas": [tema]})
    assert "não dá para excluir" in cliente.post(url, {"acao": "excluir", "pk": tema.pk}
                                                  ).content.decode()
    r = cliente.post(reverse("palestras:respostas"), {"tipo": "Confirmação",
                                                      "mensagem": "Olá {solicitante}"})
    assert r.status_code == 302 and RespostaPadrao.objects.count() == 1
    r = cliente.post(reverse("palestras:palestrantes"), {"nome": "Ana", "lotacao": "DPCAP",
                                                          "municipio": "", "servidor": ""})
    assert r.status_code == 302
    ana = Palestrante.objects.get()
    r = cliente.post(reverse("palestras:palestrantes"), {
        "pk": ana.pk, f"p{ana.pk}-nome": "Ana Paula", f"p{ana.pk}-lotacao": "DPCAP",
        f"p{ana.pk}-municipio": "", f"p{ana.pk}-servidor": ""})
    assert r.status_code == 302
    ana.refresh_from_db()
    assert ana.nome == "Ana Paula"
    r = cliente.get(reverse("palestras:buscar_palestrantes"), {"q": "paula"})
    assert r.json()["resultados"][0]["id"] == ana.pk


def test_agenda(ascom):
    hoje = timezone.localdate()
    p = services.criar(ascom, {"data_solicitacao": hoje, "solicitante": "X",
                               "data_inicio_evento": hoje, "hora_inicio": time(9)})
    itens = {i.chave: i for i in agenda.compromissos_de(ascom, hoje, hoje, ["palestra"])}
    assert itens[f"palestra-{p.pk}"].hora == "09:00"
