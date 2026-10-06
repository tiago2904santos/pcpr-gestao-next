"""E3: painel de Eventos Sociais (números sobre o que a pessoa vê, filas com o mesmo
recorte, despacho da DG) e lembretes diários (uma vez só por data de referência, janela de
30 dias, destinatários certos, pela rotina diária)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.eventos import lembretes, painel
from gestao.eventos.models import Lembrete, Movimento, Solicitacao
from gestao.identidade.models import Usuario
from gestao.plataforma import rotinas
from gestao.plataforma.models import Notificacao

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


def _s(dono, status: str, **campos) -> Solicitacao:
    hoje = timezone.localdate()
    return Solicitacao.objects.create(criado_por=dono, status=status,
                                      data_solicitacao=campos.pop("pedido", hoje), **campos)


def test_painel_conta_so_o_que_a_pessoa_ve(client: Client):
    hoje = timezone.localdate()
    ana, bia, dg = _usuario("ana"), _usuario("bia"), _usuario("dg", "GESTOR_DG")
    _s(ana, "aguardando_despacho", data_inicio_evento=hoje + timedelta(days=3),
       unidade_movel=True)
    _s(ana, "deferida", data_inicio_evento=hoje + timedelta(days=10))
    _s(ana, "atendida", data_inicio_evento=hoje - timedelta(days=3))
    _s(ana, "nao_atendida")
    _s(bia, "cancelada", data_inicio_evento=hoje + timedelta(days=5))
    r = painel.resumo(ana, hoje)
    assert (r.no_mes, r.aguardando, r.deferidas_ano, r.atendidas_ano) == (4, 1, 2, 1)
    assert r.decididas_ano == 3 and r.percentual == 67
    assert (r.proximos, r.proximos_unidade_movel) == (2, 1)  # cancelada não conta
    assert painel.resumo(dg, hoje).no_mes == 5  # a DG vê todas
    client.force_login(ana)
    html = client.get(reverse("eventos:painel")).content.decode()
    assert "Aguardando despacho" in html and "?fila=deferidas_ano" in html
    assert client.get(reverse("eventos:painel"), {"meses": "24"}).status_code == 200
    assert client.get(reverse("eventos:painel"), {"meses": "x"}).status_code == 200


def test_painel_vazio_e_tempo_medio_do_despacho(client: Client):
    ana, dg = _usuario("ana"), _usuario("dg", "GESTOR_DG")
    client.force_login(ana)
    html = client.get(reverse("eventos:painel")).content.decode()
    assert "Nenhuma solicitação registrada" in html and "Sem registros" in html
    s = _s(ana, "deferida", decisao_dg="atender")
    envio = Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.ENVIO, usuario=ana)
    decisao = Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.DECISAO, usuario=dg)
    Movimento.objects.filter(pk=decisao.pk).update(em=envio.em + timedelta(days=2))
    d = painel.despacho(dg, timezone.localdate(), 0)
    assert d.media_dias == 2.0 and d.decididas == 1 and d.atender == 1


def test_lembretes_uma_vez_e_para_quem_deve():
    hoje = timezone.localdate()
    ana, dg = _usuario("ana"), _usuario("dg", "GESTOR_DG")
    confirmar = _s(ana, "deferida", data_inicio_evento=hoje - timedelta(days=2),
                   data_fim_evento=hoje - timedelta(days=1))
    _s(ana, "deferida", data_inicio_evento=hoje - timedelta(days=60))  # fora da janela
    proximo = _s(ana, "aguardando_despacho", data_inicio_evento=hoje + timedelta(days=1))
    _s(ana, "aguardando_despacho", data_inicio_evento=hoje + timedelta(days=20))  # longe
    parada = _s(ana, "devolvida")
    m = Movimento.objects.create(solicitacao=parada, acao=Movimento.Acao.DEVOLUCAO,
                                 usuario=dg)
    Movimento.objects.filter(pk=m.pk).update(em=timezone.make_aware(
        datetime.combine(hoje - timedelta(days=5), time(10))))
    enviados = lembretes.enviar_lembretes(hoje)
    assert enviados == {"confirmar_atendimento": 1, "despacho_proximo": 1,
                        "devolucao_parada": 1}
    assert Notificacao.objects.get(usuario=dg).titulo == (
        f"Solicitação #{proximo.pk} aguarda despacho: evento amanhã")
    assert set(Notificacao.objects.filter(usuario=ana).values_list("link", flat=True)) == {
        reverse("eventos:solicitacao", args=[confirmar.pk]) + "#encerramento",
        reverse("eventos:solicitacao", args=[parada.pk])}
    assert sum(lembretes.enviar_lembretes(hoje).values()) == 0  # não repete
    # A data mudou: vale de novo.
    Solicitacao.objects.filter(pk=proximo.pk).update(data_inicio_evento=hoje + timedelta(days=2))
    assert lembretes.enviar_lembretes(hoje)["despacho_proximo"] == 1
    assert Lembrete.objects.count() == 4


def test_lembretes_entram_na_rotina_diaria():
    assert "lembretes das solicitações de evento" in dict(rotinas._ROTINAS)


def test_reenvio_nao_dispara_devolucao_parada():
    hoje = timezone.localdate()
    ana, dg = _usuario("ana"), _usuario("dg", "GESTOR_DG")
    s = _s(ana, "aguardando_despacho")
    m = Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.DEVOLUCAO, usuario=dg)
    Movimento.objects.filter(pk=m.pk).update(em=timezone.now() - timedelta(days=5))
    assert lembretes.enviar_lembretes(hoje)["devolucao_parada"] == 0  # já reenviada
