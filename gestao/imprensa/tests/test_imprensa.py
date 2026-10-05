"""Atendimento à imprensa de ponta a ponta no servidor: acesso pelo papel, criar, salvar
sozinho (autosave), veículo novo pelo nome, andamento com histórico, filas e filtros da
lista, exportação CSV, painel, cadastros de apoio (só quem administra) e a fonte da agenda."""

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
from gestao.imprensa import historico, services
from gestao.imprensa.models import Andamento, Atendimento, Integrante, Veiculo
from gestao.plataforma import agenda
from gestao.plataforma.navegacao import navegacao_para

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


@pytest.fixture
def ascom():
    return _usuario("ascom", "ASCOM_IMPRENSA")


@pytest.fixture
def admin():
    return _usuario("admin", "ADMINISTRADOR")


@pytest.fixture
def cliente(ascom):
    c = Client()
    c.force_login(ascom)
    return c


def _dados(**extra) -> dict:
    hoje = timezone.localdate()
    return {"data": hoje, "horario": time(9, 30), "jornalista": "  Ana   Paula ",
            "contato": "41 9999-0000", "pedido": "Dados da operação\n\n\nde ontem",
            "deadline": hoje + timedelta(days=1), **extra}


def _post(**extra) -> dict:
    hoje = timezone.localdate()
    base = {"data": f"{hoje:%d/%m/%Y}", "horario": "9h30", "jornalista": "Ana Paula",
            "contato": "41 9999-0000", "pedido": "Dados da operação",
            "deadline": f"{hoje + timedelta(days=1):%d/%m/%Y}", "veiculo": "",
            "veiculo_novo": "", "responsavel": "", "horario_resposta": "",
            "responsavel_resposta": "", "fonte": "", "inicio_pedido": "", "final_pedido": "",
            "resposta": ""}
    base.update(extra)
    return base


def test_so_o_papel_acessa_e_o_menu_aparece_so_para_ele(ascom):
    sem = _usuario("sem", "OPERADOR_VIAGENS")
    c = Client()
    c.force_login(sem)
    assert c.get(reverse("imprensa:painel")).status_code == 403
    assert c.get(reverse("imprensa:lista")).status_code == 403
    assert c.post(reverse("imprensa:novo"), _post()).status_code == 403

    class Req:
        path = "/"
        user = sem
    assert all(m["chave"] != "imprensa" for m in navegacao_para(Req())["modulos"])
    Req.user = ascom
    modulo = next(m for m in navegacao_para(Req())["modulos"] if m["chave"] == "imprensa")
    # Cadastros de apoio ficam com quem administra: o papel não vê o menu "Cadastros".
    assert [g["rotulo"] for g in modulo["grupos"]] == ["Atendimento"]


def test_criar_pela_tela_limpa_textos_e_cria_veiculo_pelo_nome(cliente, ascom):
    Veiculo.objects.create(nome="RPC")
    r = cliente.post(reverse("imprensa:novo"), _post(
        jornalista="  Ana   Paula ", veiculo_novo="rpc", pedido="Linha 1\n\n\n\nLinha 2"))
    a = Atendimento.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("imprensa:atendimento",
                                                             args=[a.pk])
    assert a.jornalista == "Ana Paula" and a.pedido == "Linha 1\n\nLinha 2"
    assert a.veiculo.nome == "RPC" and Veiculo.objects.count() == 1  # sem diferença de caixa
    assert a.horario == time(9, 30) and a.situacao == "em_andamento" and a.criado_por == ascom
    cliente.post(reverse("imprensa:novo"), _post(veiculo_novo="Rádio Clube"))
    assert Veiculo.objects.filter(nome="Rádio Clube").exists()


def test_novo_com_erros_mostra_e_nao_grava(cliente):
    hoje = timezone.localdate()
    r = cliente.post(reverse("imprensa:novo"), _post(
        jornalista="", horario="25h", deadline=f"{hoje - timedelta(days=1):%d/%m/%Y}"))
    html = r.content.decode()
    assert r.status_code == 200 and not Atendimento.objects.exists()
    assert "O deadline não pode ser anterior à data do pedido." in html
    assert "Use hh:mm" in html


def test_autosave_grava_e_avisa_o_que_impede(cliente, ascom):
    a = services.criar(ascom, _dados())
    url = reverse("imprensa:autosave", args=[a.pk])
    r = cliente.post(url, _post(resposta="Nota enviada", horario_resposta="10h05",
                                fonte="Del. X\n\nIML", inicio_pedido="09h40\n\n09h50"))
    assert r.json()["salvo"] is True and r.json()["recarregar"] is False
    a.refresh_from_db()
    assert a.resposta == "Nota enviada" and a.horario_resposta == time(10, 5)
    folha = cliente.get(reverse("imprensa:atendimento", args=[a.pk])).content.decode()
    assert "Del. X" in folha and "09h50" in folha  # tabela das fontes alinhadas
    r = cliente.post(url, _post(jornalista=""))
    assert r.json()["salvo"] is False and "Jornalista" in r.json()["mensagem"]
    r = cliente.post(url, _post(veiculo_novo="Band"))
    assert r.json() == {"salvo": True, "recarregar": True, "em": r.json()["em"]}


def test_atendido_nao_perde_a_resposta(ascom):
    a = services.criar(ascom, _dados(resposta="Nota"))
    services.registrar_andamento(ascom, a.pk, "atendido")
    with pytest.raises(services.AtendimentoInvalido, match="atendido") as exc:
        services.salvar(ascom, a.pk, {"resposta": ""})
    assert exc.value.campo == "resposta"


def test_andamento_pela_tela_com_historico(cliente, ascom):
    a = services.criar(ascom, _dados())
    url = reverse("imprensa:andamento", args=[a.pk])
    r = cliente.post(url, {"nova_situacao": "atendido", "anotacao": ""})
    assert r.status_code == 400 and "Para marcar como atendido" in r.content.decode()
    r = cliente.post(url, {"nova_situacao": "", "anotacao": ""})
    assert r.status_code == 400 and "Escolha a nova situação." in r.content.decode()
    r = cliente.post(url, {"nova_situacao": "aguardando_fonte",
                           "anotacao": "Aguardando o delegado"})
    assert r.status_code == 302
    r = cliente.post(url, {"nova_situacao": "atendido", "anotacao": "Nota enviada às 11h"})
    a.refresh_from_db()
    assert a.situacao == "atendido" and a.andamento == "Nota enviada às 11h"
    assert list(Andamento.objects.values_list("situacao_anterior", "situacao_nova")) == [
        ("aguardando_fonte", "atendido"), ("em_andamento", "aguardando_fonte")]
    eventos = historico.do_atendimento(a)
    textos = [e.descricao for e in eventos]
    assert textos[0] == "Situação: Atendido — Nota enviada às 11h"
    assert "Atendimento registrado" in textos
    folha = cliente.get(reverse("imprensa:atendimento", args=[a.pk])).content.decode()
    assert "Aguardando o delegado" in folha


def test_historico_junta_edicoes_seguidas(cliente, ascom):
    a = services.criar(ascom, _dados(jornalista="Ana Paula", pedido="Dados da operação"))
    url = reverse("imprensa:autosave", args=[a.pk])
    cliente.post(url, _post(contato="outro"))
    cliente.post(url, _post(contato="outro", resposta="Texto"))
    eventos = historico.do_atendimento(a)
    alterados = [e for e in eventos if e.acao == "alterado"]
    assert len(alterados) == 1 and alterados[0].descricao == "Alterou contato e resposta"


def test_lista_filas_busca_filtros_e_exportacao(cliente, ascom):
    hoje = timezone.localdate()
    rpc = Veiculo.objects.create(nome="RPC")
    mariana = Integrante.objects.create(nome="Mariana")
    aberto = services.criar(ascom, _dados(jornalista="Bruno", veiculo=rpc,
                                          deadline=hoje, data=hoje))
    Atendimento.objects.filter(pk=aberto.pk).update(deadline=hoje - timedelta(days=1),
                                                    data=hoje - timedelta(days=3))
    atendido = services.criar(ascom, _dados(jornalista="Carla", resposta="ok",
                                            responsavel_resposta=mariana))
    services.registrar_andamento(ascom, atendido.pk, "atendido")
    services.criar(ascom, _dados(jornalista="Davi", pedido="Sobre o IML; nada a ver"))
    lista = reverse("imprensa:lista")
    html = cliente.get(lista).content.decode()
    assert "Bruno · RPC" in html and "Deadline vencido em" in html
    assert 'Em aberto <span class="aba__contagem">2</span>' in html
    html = cliente.get(lista, {"fila": "atendidos"}).content.decode()
    assert "Carla" in html and "Bruno" not in html
    html = cliente.get(lista, {"q": "iml"}).content.decode()
    assert "Davi" in html and "Carla" not in html
    assert 'Todos <span class="aba__contagem">1</span>' in html  # contagens com a busca
    html = cliente.get(lista, {"responsavel": mariana.pk}).content.decode()
    assert "Carla" in html and "Davi" not in html  # também pela resposta
    html = cliente.get(lista, {"vencidos": "1"}).content.decode()
    assert "Bruno" in html and "Davi" not in html
    inicio = f"{hoje - timedelta(days=1):%d/%m/%Y}"
    html = cliente.get(lista, {"inicio": inicio}).content.decode()
    assert "Bruno" not in html and "Carla" in html
    html = cliente.get(lista, {"inicio": "lixo", "veiculo": "x"}).content.decode()
    assert "Bruno" in html  # filtro inválido é ignorado
    r = cliente.get(reverse("imprensa:exportar"), {"fila": "abertos"})
    texto = r.content.decode("utf-8")
    assert r["Content-Type"].startswith("text/csv") and texto.startswith("﻿")
    linhas = list(csv.reader(io.StringIO(texto.lstrip("﻿")), delimiter=";"))
    assert linhas[0][:3] == ["Data", "Horário", "Jornalista"] and len(linhas) == 3
    assert {linha[2] for linha in linhas[1:]} == {"Bruno", "Davi"}


def test_lista_vazia_e_painel(cliente, ascom):
    html = cliente.get(reverse("imprensa:lista")).content.decode()
    assert "Nenhum atendimento ainda" in html
    html = cliente.get(reverse("imprensa:painel")).content.decode()
    assert "Nada em aberto" in html and "Nenhum pedido registrado" in html
    rpc = Veiculo.objects.create(nome="RPC")
    mariana = Integrante.objects.create(nome="Mariana")
    a = services.criar(ascom, _dados(veiculo=rpc, responsavel=mariana, resposta="ok"))
    services.registrar_andamento(ascom, a.pk, "atendido")
    services.criar(ascom, _dados(jornalista="Outro"))
    html = cliente.get(reverse("imprensa:painel")).content.decode()
    assert "50% dos pedidos" in html and "Mariana" in html and "RPC" in html
    assert "Cadastros de apoio" not in html


def test_cadastros_so_para_quem_administra(cliente, admin, ascom):
    assert cliente.get(reverse("imprensa:equipe")).status_code == 403
    with pytest.raises(PermissionDenied):
        services.salvar_cadastro(ascom, "equipe", "Mariana")
    c = Client()
    c.force_login(admin)
    url = reverse("imprensa:equipe")
    assert c.post(url, {"nome": "  Mariana  "}).status_code == 302
    r = c.post(url, {"nome": "mariana"})
    assert "Já existe" in r.content.decode()
    m = Integrante.objects.get()
    c.post(url, {"nome": "Mariana S.", "pk": m.pk})
    m.refresh_from_db()
    assert m.nome == "Mariana S."
    services.criar(ascom, _dados(responsavel_resposta=m))
    r = c.post(url, {"acao": "excluir", "pk": m.pk})
    assert "não dá para excluir" in r.content.decode() and Integrante.objects.exists()
    html = c.get(url).content.decode()
    assert "1 atendimento" in html
    v = Veiculo.objects.create(nome="Band")
    c.post(reverse("imprensa:veiculos"), {"acao": "excluir", "pk": v.pk})
    assert not Veiculo.objects.exists()
    assert c.post(url, {"acao": "excluir", "pk": 999}).status_code == 404


def test_fonte_da_agenda(ascom):
    hoje = timezone.localdate()
    a = services.criar(ascom, _dados(deadline=hoje))
    fechado = services.criar(ascom, _dados(jornalista="Zé", deadline=hoje, resposta="ok"))
    services.registrar_andamento(ascom, fechado.pk, "atendido")
    itens = {c.chave: c for c in agenda.compromissos_de(ascom, hoje, hoje, ["imprensa"])}
    assert itens[f"imprensa-{a.pk}"].prazo and not itens[f"imprensa-{a.pk}"].encerrado
    assert itens[f"imprensa-{fechado.pk}"].encerrado
    sem = _usuario("sem", "OPERADOR_VIAGENS")
    assert all(f.slug != "imprensa" for f in agenda.fontes_de(sem))


def test_restricao_do_banco_deadline_depois_do_pedido(ascom):
    from django.db import IntegrityError, transaction
    a = services.criar(ascom, _dados())
    with pytest.raises(IntegrityError), transaction.atomic():
        Atendimento.objects.filter(pk=a.pk).update(deadline=a.data - timedelta(days=1))


def test_permissoes_por_escrita(ascom):
    consulta = _usuario("consulta", "CONSULTA")
    with pytest.raises(PermissionDenied):
        services.criar(consulta, _dados())
    a = services.criar(ascom, _dados())
    with pytest.raises(PermissionDenied):
        services.registrar_andamento(consulta, a.pk, "atendido", "x")
