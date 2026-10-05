"""Rotina diária e avisos da prestação de contas: uma rodada por dia (entre processos, pela
marca no banco), rotina que falha não derruba as outras, avisos de saque/prestação/
documentos/chegada uma vez só e só para a unidade do ofício."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone

from gestao.cadastros.models import Lotacao
from gestao.identidade.models import Usuario
from gestao.plataforma import rotinas
from gestao.plataforma.models import Notificacao, RotinaDoDia
from gestao.viagens import anexos, avisos, diario, prestacao, relatorio
from gestao.viagens.models import PrestacaoContas, Trecho

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4 teste"


@pytest.fixture
def c():
    cen = cenario_completo()
    u = Usuario.objects.create_user("colega", "colega@pc.pr.gov.br", "senha-local-123",
                                    nome="Colega da ASCOM")
    u.groups.add(Group.objects.get(name="OPERADOR_VIAGENS"))
    Lotacao.objects.create(usuario=u, unidade=cen.usuarios["operador"].lotacao.unidade)
    return cen


def _p(c) -> PrestacaoContas:
    return PrestacaoContas.objects.select_related("oficio").get(
        oficio_id=c.ids["oficio_emitido"])


def _titulos(login: str) -> list[str]:
    return list(Notificacao.objects.filter(usuario__login=login)
                .values_list("titulo", flat=True))


def test_uma_rodada_por_dia_e_falha_isolada(c):
    chamadas = []
    rotinas.registrar_rotina("teste que falha", lambda hoje: 1 / 0)
    rotinas.registrar_rotina("teste que conta", lambda hoje: chamadas.append(hoje) or "ok")
    try:
        rotinas.esquecer_o_dia()
        assert rotinas.rodar_se_for_hora() is True
        marca = RotinaDoDia.objects.get(dia=timezone.localdate())
        assert marca.resultado["teste que falha"] == "falhou"
        assert marca.resultado["teste que conta"] == "ok"
        rotinas.esquecer_o_dia()  # outro processo: a marca no banco impede repetir
        assert rotinas.rodar_se_for_hora() is False
        assert len(chamadas) == 1
    finally:
        rotinas._ROTINAS[:] = [(n, f) for n, f in rotinas._ROTINAS if not n.startswith("teste")]
        rotinas.esquecer_o_dia()


def test_avisos_de_saque_e_prestacao_vencida_uma_vez(c):
    p = _p(c)
    a, _ = prestacao.ativos().filter(prestacao=p).order_by("servidor__nome")
    hoje = timezone.localdate()
    prestacao.salvar_solicitacao(c.usuarios["operador"], a.pk, numero="1",
                                 liberacao=hoje - timedelta(days=30),
                                 prazo=hoje - timedelta(days=20))
    assert avisos.avisar_prazos(hoje) >= 2
    titulos = _titulos("colega")
    assert any(t.startswith("Prazo de saque vencido: ") for t in titulos)
    assert any(t.startswith("Prestação vencida: ") for t in titulos)
    assert not _titulos("outra")  # outra unidade não recebe
    assert avisos.avisar_prazos(hoje) == 0  # não repete
    # Com o comprovante, o de saque não sai mais (o de prestação vencida já saiu).
    Notificacao.objects.all().delete()
    anexos.anexar(c.usuarios["operador"], p.pk, "comprovante", servidor_pk=a.pk,
                  nome="c.pdf", conteudo=PDF)
    avisos.avisar_prazos(hoje)
    assert not any(t.startswith("Prazo de saque") for t in _titulos("colega"))


def test_saque_vence_em_n_dias_e_documentos(c):
    p = _p(c)
    a, _ = prestacao.ativos().filter(prestacao=p).order_by("servidor__nome")
    hoje = timezone.localdate()
    op = c.usuarios["operador"]
    prestacao.salvar_solicitacao(op, a.pk, numero="1", liberacao=hoje,
                                 prazo=hoje + timedelta(days=2))
    d = diario.obter(p)
    diario.salvar_linhas(op, d.pk, {linha.pk: {"km_inicial": 1 + i * 500,
                                               "km_final": 400 + i * 500}
                                    for i, linha in enumerate(diario.linhas(d))})
    rt = relatorio.obter(p)
    relatorio.salvar(op, rt.pk, {"motivo": "a", "atividade": "b", "conclusao": "c"})
    avisos.avisar_prazos(hoje)
    titulos = _titulos("colega")
    assert any(t.startswith("Saque vence em 2 dias: ") for t in titulos)
    assert any(t.startswith("Documentos gerados: ") for t in titulos)
    anexos.anexar(op, p.pk, "db_assinado", nome="db.pdf", conteudo=PDF)
    anexos.anexar(op, p.pk, "rt_assinado", servidor_pk=a.pk, nome="rt.pdf", conteudo=PDF)
    avisos.avisar_prazos(hoje)
    assert any(t.startswith("Documentos assinados recebidos: ") for t in _titulos("colega"))


def test_equipe_chegou(c):
    p = _p(c)
    ultimo = Trecho.objects.filter(oficio=p.oficio).order_by("-ordem").first()
    agora = timezone.now()
    Trecho.objects.filter(pk=ultimo.pk).update(saida_em=agora - timedelta(hours=8),
                                               chegada_em=agora - timedelta(hours=2))
    assert avisos.avisar_chegadas() == 1
    assert any("chegou de viagem" in t for t in _titulos("colega"))
    assert avisos.avisar_chegadas() == 0


def test_comando(c, capsys):
    rotinas.esquecer_o_dia()
    call_command("rodar_rotinas_diarias")
    saida = capsys.readouterr().out
    assert "avisos da prestação de contas:" in saida
    call_command("rodar_rotinas_diarias")
    assert "já rodaram" in capsys.readouterr().out
    rotinas.esquecer_o_dia()
