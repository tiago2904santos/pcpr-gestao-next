"""Viagem realizada (módulo 9b-2): copiar os trechos do ofício, corrigir horários (com a
sequência conferida), recalcular as diárias sem mudar o ofício, o diário seguir os realizados
guardando os km, o RT receber a diária nova (se ainda automática) e o texto das mudanças,
voltar ao do ofício, trava e permissões."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.viagens import diario, prestacao, realizado, relatorio
from gestao.viagens.models import Oficio, PrestacaoContas, RelatorioTecnico

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _p(c) -> PrestacaoContas:
    return PrestacaoContas.objects.select_related("oficio__sede").get(
        oficio_id=c.ids["oficio_emitido"])


def test_ajustar_copia_e_nao_muda_o_oficio(c):
    p = _p(c)
    op = c.usuarios["operador"]
    antes = list(p.oficio.trechos.order_by("ordem").values_list("saida_em", "chegada_em"))
    realizado.ajustar(op, p.pk)
    realizado.ajustar(op, p.pk)  # a segunda vez não duplica
    lista = realizado.trechos(p)
    assert [(t.saida_em, t.chegada_em) for t in lista] == antes
    p.refresh_from_db()
    assert p.diarias_realizadas_total == p.oficio.diarias_total
    assert realizado.alteracoes(p) == []


def test_horarios_novos_recalculam_e_entram_no_rt(c):
    p = _p(c)
    op = c.usuarios["operador"]
    rt = relatorio.obter(p)
    diaria_antes = rt.diaria
    realizado.ajustar(op, p.pk)
    _, volta = realizado.trechos(p)
    # Voltou dois dias depois: mais diárias.
    nova_saida = volta.saida_em + timedelta(days=2)
    nova_chegada = volta.chegada_em + timedelta(days=2)
    realizado.salvar(op, p.pk, {volta.pk: (nova_saida, nova_chegada)})
    p.refresh_from_db()
    oficio = Oficio.objects.get(pk=p.oficio_id)
    assert p.diarias_realizadas_total > oficio.diarias_total  # o ofício não muda
    ps = prestacao.ativos().filter(prestacao=p).first()
    assert prestacao.diaria_liberada(ps) == realizado.por_servidor(p)
    rt.refresh_from_db()
    assert rt.diaria != diaria_antes and rt.diaria == relatorio.diaria_padrao(p)
    assert "a diária (por servidor) passou de" in rt.info_complementares
    assert any(a.startswith("saída (") for a in realizado.alteracoes(p))
    # A diária escrita à mão não é trocada.
    RelatorioTecnico.objects.filter(pk=rt.pk).update(diaria="R$ 10,00 (à mão)")
    realizado.salvar(op, p.pk, {volta.pk: (nova_saida + timedelta(hours=1),
                                           nova_chegada + timedelta(hours=1))})
    rt.refresh_from_db()
    assert rt.diaria == "R$ 10,00 (à mão)"


def test_sequencia_conferida(c):
    p = _p(c)
    op = c.usuarios["operador"]
    realizado.ajustar(op, p.pk)
    ida, volta = realizado.trechos(p)
    with pytest.raises(realizado.AjusteInvalido, match="chegada precisa ser depois"):
        realizado.salvar(op, p.pk, {ida.pk: (ida.saida_em, ida.saida_em - timedelta(hours=1))})
    with pytest.raises(realizado.AjusteInvalido, match="sai antes da chegada"):
        realizado.salvar(op, p.pk, {volta.pk: (ida.chegada_em - timedelta(hours=1),
                                               ida.chegada_em + timedelta(hours=2))})


def test_diario_segue_os_realizados_e_guarda_os_km(c):
    p = _p(c)
    op = c.usuarios["operador"]
    d = diario.obter(p)
    a, _ = diario.linhas(d)
    diario.salvar_linhas(op, d.pk, {a.pk: {"km_inicial": 100, "km_final": 400}})
    realizado.ajustar(op, p.pk)
    diario.sincronizar(d)
    novas = diario.linhas(d)
    assert all(linha.realizado_id for linha in novas)
    assert novas[0].km_final == 400  # a linha do mesmo trecho guardou os km
    ida, _ = realizado.trechos(p)
    realizado.salvar(op, p.pk, {ida.pk: (ida.saida_em + timedelta(hours=1),
                                         ida.chegada_em + timedelta(hours=1))})
    dados = diario.dados_do_documento(d)
    esperada = timezone.localtime(ida.saida_em + timedelta(hours=1))
    assert dados["linhas"][0]["hora_saida"] == f"{esperada:%H:%M}"
    realizado.desfazer(op, p.pk)
    diario.sincronizar(d)
    assert all(linha.realizado_id is None for linha in diario.linhas(d))
    assert diario.linhas(d)[0].km_final == 400


def test_trava_e_permissoes_e_tela(c):
    p = _p(c)
    op_cliente, outra = Client(), Client()
    op_cliente.force_login(c.usuarios["operador"])
    outra.force_login(c.usuarios["outra"])
    url = reverse("viagens:viagem_realizada", args=[p.pk, "ajustar"])
    assert outra.post(url).status_code == 404
    r = op_cliente.post(reverse("viagens:viagem_realizada", args=[p.pk, "ajustar"]))
    assert r["Location"].endswith("#realizada")
    html = op_cliente.get(reverse("viagens:diario", args=[p.pk])).content.decode()
    assert "Salvar horários e recalcular" in html
    volta = realizado.trechos(p)[1]
    r = op_cliente.post(reverse("viagens:viagem_realizada", args=[p.pk, "salvar"]), {
        **{f"r-{t.pk}-{campo}": valor for t in realizado.trechos(p) for campo, valor in (
            ("saida_data", f"{timezone.localtime(t.saida_em):%d/%m/%Y}"),
            ("saida_hora", f"{timezone.localtime(t.saida_em):%H:%M}"),
            ("chegada_data", f"{timezone.localtime(t.chegada_em):%d/%m/%Y}"),
            ("chegada_hora", f"{timezone.localtime(t.chegada_em):%H:%M}"))},
        f"r-{volta.pk}-chegada_hora": "99:99"}, follow=True)
    assert "informe data (dd/mm/aaaa) e hora (hh:mm)" in r.content.decode()
    op = c.usuarios["operador"]
    for ps in prestacao.ativos().filter(prestacao=p):
        prestacao.finalizar(op, ps.pk, "Teste da trava.")
    with pytest.raises(realizado.AjusteInvalido, match="reabra"):
        realizado.desfazer(op, p.pk)
    assert realizado.por_servidor(p) is None or isinstance(realizado.por_servidor(p), Decimal)
