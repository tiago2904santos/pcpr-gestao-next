"""PL2a: "Encaminhar à DG" — a palestra vira o rascunho de uma solicitação de evento com o
que já tem (datas, município, tipo, solicitante, contato, descrição com tema, palestrante,
horário e público), as duas ficam ligadas, não se encaminha duas vezes nem a cancelada, e o
que a DG faz na solicitação aparece no histórico da palestra."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.eventos.models import Movimento, Solicitacao
from gestao.identidade.models import Usuario
from gestao.palestras import encaminhamento, historico
from gestao.palestras.models import Palestra, Palestrante, Tema

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    u = Usuario.objects.create_user("ascom", "ascom@teste.invalid", None, nome="Ascom")
    u.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
    cwb = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                          defaults={"nome": "Curitiba", "uf": "PR"})[0]
    dia = timezone.localdate() + timedelta(days=15)
    p = Palestra.objects.create(
        data_solicitacao=timezone.localdate(), solicitante="Colégio Exemplo",
        telefone="41999998888", email="contato@escola.invalid",
        evento=Palestra.Evento.PCPR_NA_COMUNIDADE, data_inicio_evento=dia,
        hora_inicio=time(9, 30), municipio=cwb, local="Ginásio", quantidade_publico=200,
        criado_por=u)
    p.temas.add(Tema.objects.create(nome="Segurança digital"))
    p.palestrantes.add(Palestrante.objects.create(nome="Agente Exemplo"))
    return u, p, dia


def test_encaminhar_cria_o_rascunho_ligado(cenario):
    u, p, dia = cenario
    s = encaminhamento.encaminhar(u, p.pk)
    assert s.status == Solicitacao.Status.RASCUNHO and s.criado_por == u
    assert (s.data_inicio_evento, s.data_fim_evento) == (dia, dia)
    assert s.municipio == p.municipio and "COMUNIDADE" in s.tipo_evento.nome.upper()
    assert s.solicitante_nome == "Colégio Exemplo"
    assert s.contato == "41999998888 contato@escola.invalid"
    assert "Tema: Segurança digital" in s.descricao_complementar
    assert "Palestrante: Agente Exemplo" in s.descricao_complementar
    assert "Horário: 09:30" in s.descricao_complementar
    assert "Público previsto: 200 pessoas" in s.descricao_complementar
    p.refresh_from_db()
    assert p.solicitacao_dg == s
    assert p.andamentos.get().anotacao.startswith(f"Solicitação de evento #{s.pk} criada")
    with pytest.raises(encaminhamento.EncaminhamentoInvalido, match="Já encaminhada"):
        encaminhamento.encaminhar(u, p.pk)
    # O que a DG faz volta para o histórico da palestra.
    Movimento.objects.create(solicitacao=s, acao=Movimento.Acao.ENVIO, usuario=u,
                             status_anterior="rascunho")
    textos = [e.descricao for e in historico.da_palestra(p)]
    assert any(t.startswith(f"Solicitação #{s.pk} — Solicitação enviada") for t in textos)


def test_tela_e_recusas(cenario):
    u, p, _dia = cenario
    cli = Client()
    cli.force_login(u)
    folha = cli.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert "Encaminhar à DG" in folha
    r = cli.post(reverse("palestras:encaminhar_dg", args=[p.pk]))
    s = Solicitacao.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("eventos:solicitacao",
                                                              args=[s.pk])
    folha = cli.get(reverse("palestras:palestra", args=[p.pk])).content.decode()
    assert f"Solicitação à DG #{s.pk}" in folha and "Encaminhar à DG" not in folha
    outra = Palestra.objects.create(data_solicitacao=timezone.localdate(), solicitante="X",
                                    status=Palestra.Status.CANCELADA, criado_por=u)
    with pytest.raises(encaminhamento.EncaminhamentoInvalido, match="cancelada"):
        encaminhamento.encaminhar(u, outra.pk)
    leitor = Usuario.objects.create_user("zeca", "z@teste.invalid", None, nome="Zeca")
    cli.force_login(leitor)
    assert cli.post(reverse("palestras:encaminhar_dg", args=[p.pk])).status_code == 403
