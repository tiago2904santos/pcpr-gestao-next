"""E4: a viagem que nasce da solicitação de evento deferida — quem gera, para qual unidade,
o que a viagem traz, uma só por solicitação, a folha mostra e, quando o evento não
acontece, a viagem sem documento é cancelada (com documento, a unidade é avisada)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Lotacao, Municipio, TipoViagem
from gestao.eventos import solicitacoes
from gestao.eventos.models import (
    Equipe,
    Movimento,
    OrgaoResponsavel,
    Servico,
    Solicitacao,
    TipoEvento,
)
from gestao.identidade.models import Usuario
from gestao.plataforma.models import Notificacao
from gestao.viagens import de_eventos
from gestao.viagens.models import Roteiro, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _dg() -> Usuario:
    u = Usuario.objects.create_user("dg", "dg@teste.invalid", None, nome="Diretoria")
    u.groups.add(Group.objects.get(name="GESTOR_DG"))
    return u


def _deferida(dono, dg, *, equipe: str = "Alfa") -> Solicitacao:
    hoje = timezone.localdate()
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    s = solicitacoes.criar(dono, {
        "data_solicitacao": hoje, "data_inicio_evento": hoje + timedelta(days=20),
        "data_fim_evento": hoje + timedelta(days=21), "municipio": curitiba,
        "tipo_evento": TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0],
        "solicitante_nome": "Escola X", "solicitante_cargo_unidade": "Direção",
        "orgao_responsavel": OrgaoResponsavel.objects.first(), "local_evento": "Ginásio",
        "descricao_complementar": "Emissão de CIN", "tipo_operacao": "diaria"},
        solicitacoes.Estrutura(
            servicos={Servico.objects.get(nome="Emissão de CIN").pk: ""},
            equipes={Equipe.objects.get_or_create(nome=equipe)[0].pk: 3}))
    solicitacoes.enviar(dono, s.pk)
    return solicitacoes.despachar(dg, s.pk, "atender")


def test_dg_gera_a_viagem_com_o_que_a_solicitacao_sabe(c, django_capture_on_commit_callbacks):
    dg, operador = _dg(), c.usuarios["operador"]
    ascom = operador.lotacao.unidade
    tipo = TipoViagem.objects.create(nome="PCPR na Comunidade")
    s = _deferida(operador, dg, equipe=ascom.sigla or ascom.nome)
    info = de_eventos.resumo(dg, s)
    assert info["pode_gerar"] and info["sugerida"] == ascom.pk  # equipe com o nome da unidade
    with django_capture_on_commit_callbacks(execute=True):
        v = de_eventos.gerar(dg, s, ascom.pk)
    v.refresh_from_db()
    assert v.unidade == ascom and v.data_inicio == s.data_inicio_evento
    assert v.data_fim == s.data_fim_evento and f"(Solicitação #{s.pk})" in v.motivo
    assert v.titulo.startswith("Curitiba/PR — ") and list(v.tipos.all()) == [tipo]
    assert [d.municipio.nome for d in v.destinos.all()] == ["Curitiba"]
    assert Movimento.objects.filter(solicitacao=s, acao="viagem").exists()
    assert Notificacao.objects.filter(usuario=operador, titulo__contains=f"#{s.pk}").exists()
    with pytest.raises(ValueError, match="já tem viagem"):
        de_eventos.gerar(dg, s, ascom.pk)
    assert de_eventos.resumo(dg, s)["viagens"][0]["viagem"] == v


def test_quem_gera_e_para_qual_unidade(c):
    dg, operador, outra = _dg(), c.usuarios["operador"], c.usuarios["outra"]
    s = _deferida(operador, dg)
    consulta = c.usuarios["consulta"]
    assert not de_eventos.pode_gerar(consulta)
    with pytest.raises(PermissionDenied):
        de_eventos.gerar(consulta, s, operador.lotacao.unidade_id)
    with pytest.raises(PermissionDenied):  # não vê a solicitação
        de_eventos.gerar(outra, s, outra.lotacao.unidade_id)
    # Operador de viagens (aqui, o responsável) só gera para a própria unidade.
    with pytest.raises(ValueError, match="Escolha a unidade"):
        de_eventos.gerar(operador, s, outra.lotacao.unidade_id)
    v = de_eventos.gerar(operador, s, operador.lotacao.unidade_id)
    assert v.unidade_id == operador.lotacao.unidade_id


def test_so_deferida_com_municipio_e_data(c):
    dg, operador = _dg(), c.usuarios["operador"]
    s = solicitacoes.criar(operador, {"solicitante_nome": "X"})
    assert "precisa estar deferida" in de_eventos.motivo_que_impede(s)
    assert not de_eventos.resumo(dg, s)["pode_gerar"]


def test_nao_atendida_cancela_a_viagem_sem_documento_e_avisa_com_documento(
        c, django_capture_on_commit_callbacks):
    dg, operador = _dg(), c.usuarios["operador"]
    unidade = operador.lotacao.unidade_id
    s = _deferida(operador, dg)
    v = de_eventos.gerar(dg, s, unidade)
    solicitacoes.cancelar(operador, s.pk, "Chuva")
    v.refresh_from_db()
    assert v.cancelada and "cancelada: Chuva" in v.motivo_cancelamento
    t = _deferida(operador, dg)
    w = de_eventos.gerar(dg, t, unidade)
    Roteiro.objects.filter(pk=Roteiro.objects.filter(viagem__isnull=True).first().pk).update(
        viagem=w)
    with django_capture_on_commit_callbacks(execute=True):
        solicitacoes.cancelar(dg, t.pk, "Adiado")
    w.refresh_from_db()
    assert not w.cancelada  # tem documento: decide a unidade
    assert Notificacao.objects.filter(usuario=operador, titulo__startswith=f"Viagem #{w.pk}")


def test_folha_mostra_e_gera_pela_tela(c):
    dg, operador = _dg(), c.usuarios["operador"]
    Lotacao.objects.filter(usuario=dg).delete()
    s = _deferida(operador, dg)
    cli = Client()
    cli.force_login(dg)
    html = cli.get(reverse("eventos:solicitacao", args=[s.pk])).content.decode()
    assert 'id="viagem"' in html and "Gerar viagem" in html
    r = cli.post(reverse("eventos:gerar_viagem", args=[s.pk]),
                 {"unidade": str(operador.lotacao.unidade_id)})
    assert r.status_code == 302 and r["Location"].endswith("#viagem")
    v = Viagem.objects.get(solicitacoes_de_evento__solicitacao=s)
    html = cli.get(reverse("eventos:solicitacao", args=[s.pk])).content.decode()
    assert f"#{v.pk}" in html and "Gerar viagem" not in html
    r = cli.post(reverse("eventos:gerar_viagem", args=[s.pk]), {"unidade": "x"})
    assert r.status_code == 302  # o motivo vai na mensagem
