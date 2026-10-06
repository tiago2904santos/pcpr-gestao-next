"""Agenda com as fontes de Viagens: viagens que tocam o período, prazos de saque das diárias
(situação pela distância de hoje), feriados nacionais, permissão de cada fonte, a grade do mês
e a tela (filtros, cancelados escondidos, lista, navegação de mês)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma import agenda
from gestao.viagens import prestacao, viagem
from gestao.viagens.models import PrestacaoContas, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _viagem(c, inicio: date, fim: date | None = None, **campos) -> Viagem:
    v = viagem.criar(c.usuarios["operador"])
    Viagem.objects.filter(pk=v.pk).update(data_inicio=inicio, data_fim=fim, titulo="Feira",
                                          motivo="Apoio à feira (teste)", **campos)
    return Viagem.objects.get(pk=v.pk)


def test_grade_do_mes_domingo_a_sabado():
    c1 = agenda.Compromisso("x", "1", "Três dias", date(2026, 10, 7), date(2026, 10, 9))
    semanas = agenda.semanas_do_mes(2026, 10, [c1], date(2026, 10, 8))
    assert semanas[0][0].data == date(2026, 9, 27)  # domingo
    dias = [d for s in semanas for d in s]
    assert [d.data.day for d in dias if d.compromissos] == [7, 8, 9]
    assert next(d for d in dias if d.hoje).data == date(2026, 10, 8)
    assert agenda.mes_vizinho(2026, 12, 1) == (2027, 1)
    assert agenda.mes_vizinho(2026, 1, -1) == (2025, 12)


def test_fontes_viagem_prazo_e_feriado(c):
    hoje = timezone.localdate()
    op = c.usuarios["operador"]
    v = _viagem(c, hoje, hoje + timedelta(days=2))
    fora = _viagem(c, hoje + timedelta(days=90))
    p = PrestacaoContas.objects.get(oficio_id=c.ids["oficio_emitido"])
    ps = prestacao.ativos().filter(prestacao=p).first()
    prestacao.salvar_solicitacao(op, ps.pk, numero="1", liberacao=hoje - timedelta(days=5),
                                 prazo=hoje - timedelta(days=1))
    itens = agenda.compromissos_de(op, hoje - timedelta(days=3), hoje + timedelta(days=10))
    chaves = {i.chave for i in itens}
    assert f"viagem-{v.pk}" in chaves and f"viagem-{fora.pk}" not in chaves
    prazo = next(i for i in itens if i.fonte == "prazo_diarias")
    assert prazo.prazo and prazo.situacao == "Vencido" and prazo.tom == "perigo"
    natal = agenda.compromissos_de(op, date(2026, 12, 25), date(2026, 12, 25), ["feriados"])
    assert [(i.titulo, i.faixa) for i in natal] == [("Natal", True)]


def test_permissao_da_fonte(c):
    hoje = timezone.localdate()
    v = _viagem(c, hoje)
    outra = c.usuarios["outra"]  # de outra unidade: não vê a viagem da ASCOM
    assert all(i.chave != f"viagem-{v.pk}" for i in agenda.compromissos_de(outra, hoje, hoje))
    # Pedir uma fonte pelo nome não abre a porta: sem a permissão, a fonte nem entra.
    from django.contrib.auth.models import AnonymousUser
    assert [f.slug for f in agenda.fontes_de(AnonymousUser())] == []


def test_tela_mes_lista_filtros_e_cancelados(c):
    hoje = timezone.localdate()
    _viagem(c, hoje)
    cancelada = _viagem(c, hoje, situacao=Viagem.Situacao.CANCELADA)
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    r = cliente.get(reverse("painel:agenda"))
    html = r.content.decode()
    assert r.status_code == 200 and "Apoio à feira (teste)" in html
    # No mês, o compromisso abre o dossiê (`detalhe=<chave>`).
    assert f"detalhe=viagem-{cancelada.pk}" not in html  # cancelado escondido por padrão
    assert "Cancelados (1)" in html
    html = cliente.get(reverse("painel:agenda"), {"encerrados": "1"}).content.decode()
    assert f"detalhe=viagem-{cancelada.pk}" in html
    html = cliente.get(reverse("painel:agenda"), {"fonte": "feriados"}).content.decode()
    assert "Apoio à feira (teste)" not in html
    r = cliente.get(reverse("painel:agenda"), {"vista": "lista", "mes": "2026-12"})
    assert "Natal" in r.content.decode() and "dezembro de 2026" in r.content.decode().lower()
    r = cliente.get(reverse("painel:agenda"), {"mes": "2026-13"})  # mês inválido: o atual
    assert r.status_code == 200


def test_semana_e_dia():
    assert agenda.semana_de(date(2026, 10, 7)) == (date(2026, 10, 4), date(2026, 10, 10))
    assert agenda.semana_de(date(2026, 10, 4)) == (date(2026, 10, 4), date(2026, 10, 10))
    c1 = agenda.Compromisso("x", "1", "Dois dias", date(2026, 10, 9), date(2026, 10, 10))
    dias = agenda.dias_entre(date(2026, 10, 4), date(2026, 10, 10), [c1], date(2026, 10, 9))
    assert [d.data.day for d in dias if d.compromissos] == [9, 10]
    assert next(d for d in dias if d.hoje).data == date(2026, 10, 9)


def test_tela_semana_dia_e_navegacao(c):
    hoje = timezone.localdate()
    _viagem(c, hoje)
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    r = cliente.get(reverse("painel:agenda"), {"vista": "semana", "dia": hoje.isoformat()})
    html = r.content.decode()
    assert r.status_code == 200 and "Apoio à feira (teste)" in html
    assert 'aria-label="Semana anterior"' in html and 'class="agenda-semana"' in html
    domingo, _sabado = agenda.semana_de(hoje)
    assert f"dia={(hoje - timedelta(days=7)).isoformat()}" in html
    r = cliente.get(reverse("painel:agenda"), {"vista": "dia", "dia": hoje.isoformat()})
    html = r.content.decode()
    assert "Apoio à feira (teste)" in html and 'aria-label="Próximo dia"' in html
    amanha = (hoje + timedelta(days=400)).isoformat()
    r = cliente.get(reverse("painel:agenda"), {"vista": "dia", "dia": amanha})
    assert "Nada na agenda neste dia" in r.content.decode()
    r = cliente.get(reverse("painel:agenda"), {"vista": "semana", "dia": "lixo"})
    assert r.status_code == 200  # dia inválido: hoje
    assert domingo <= hoje


def test_so_os_que_eu_registrei(c):
    hoje = timezone.localdate()
    minha = _viagem(c, hoje)
    outra = _viagem(c, hoje)
    Viagem.objects.filter(pk=outra.pk).update(criado_por=c.usuarios["gestor"])
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    html = cliente.get(reverse("painel:agenda"), {"meus": "1", "vista": "lista"}).content.decode()
    assert f"viagens/{minha.pk}/" in html and f"viagens/{outra.pk}/" not in html
    html = cliente.get(reverse("painel:agenda"), {"vista": "lista"}).content.decode()
    assert f"viagens/{outra.pk}/" in html


def test_pauta_da_semana(c):
    from gestao.painel import pauta

    hoje = timezone.localdate()
    _viagem(c, hoje, hoje + timedelta(days=1))
    segunda, domingo = pauta.semana_de(hoje)
    ctx = pauta.montar(c.usuarios["operador"], segunda, domingo, hoje=hoje)
    assert ctx["titulo"] == "Pauta da semana" and len(ctx["dias"]) == 7
    dia = next(d for d in ctx["dias"] if d.data == hoje)
    assert dia.itens and not dia.itens[0].continua
    if hoje + timedelta(days=1) <= domingo:
        seguinte = next(d for d in ctx["dias"] if d.data == hoje + timedelta(days=1))
        assert seguinte.itens[0].continua
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    r = cliente.get(reverse("painel:pauta"))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    r = cliente.get(reverse("painel:pauta"), {"formato": "html", "inicio": "2026-12-21",
                                              "fim": "2026-12-27"})
    html = r.content.decode()
    assert "Pauta da semana" in html and "Natal" in html
    r = cliente.get(reverse("painel:pauta"), {"formato": "html", "inicio": "2026-01-01",
                                              "fim": "2026-12-31"})
    assert "01/01 a 03/03/2026" in r.content.decode()  # teto de 62 dias


def test_escala_pessoa_por_dia(c):
    from gestao.painel import escala
    from gestao.viagens.models import Oficio

    hoje = timezone.localdate()
    v = _viagem(c, hoje, hoje + timedelta(days=1))
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    Oficio.objects.filter(pk=oficio.pk).update(viagem=v)
    nome = oficio.viajantes.first().servidor.nome
    quadro = escala.montar(c.usuarios["operador"], hoje, 7, hoje=hoje)
    linha = next(x for x in quadro["linhas"] if x.nome == nome)
    assert linha.celulas[0] and linha.celulas[1] and not linha.celulas[2]
    assert linha.dias_fora == 2
    assert escala.montar(c.usuarios["operador"], hoje, 7, pessoa="zzz-ninguem")["linhas"] == []
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    html = cliente.get(reverse("painel:escala"), {"inicio": hoje.isoformat()}).content.decode()
    assert nome in html and "2 dias fora" in html
    r = cliente.get(reverse("painel:escala"), {"dias": "999", "inicio": "lixo"})
    assert r.status_code == 200


def test_dossie_do_compromisso(c):
    """A2c: o compromisso do mês abre o dossiê (detalhes e "Abrir no sistema"); chave de
    fora do que a pessoa vê não abre nada."""
    hoje = timezone.localdate()
    v = _viagem(c, hoje)
    cliente = Client()
    cliente.force_login(c.usuarios["operador"])
    html = cliente.get(reverse("painel:agenda"), {"detalhe": f"viagem-{v.pk}"}).content.decode()
    assert 'id="dossie"' in html and "Abrir no sistema" in html
    assert reverse("viagens:editar_viagem", args=[v.pk]) in html
    assert "Motivo" in html and "Apoio à feira (teste)" in html
    html = cliente.get(reverse("painel:agenda"), {"detalhe": "viagem-999999"}).content.decode()
    assert 'id="dossie"' not in html
