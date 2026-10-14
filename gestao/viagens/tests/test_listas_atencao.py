"""As listas de Viagens dizem o que fazer agora (o mesmo em OS, termos, planos e viagens):
a faixa "pede atenção" (urgentes e vazios) filtra a lista, os vazios saem de uma vez e a
linha mostra a estrada da viagem em andamento. A regra do tempo fica em linha_lista."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gestao.viagens import linha_lista, ordens, planos, termos, viagem
from gestao.viagens.models import OrdemServico, PlanoTrabalho, TermoAutorizacao, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def c():
    return cenario_completo()


@pytest.fixture
def operador(client, c):
    client.force_login(c.usuarios["operador"])
    return client


class TestEstadoTemporal:
    """Python puro: urgência só para o pendente; estrada só durante a viagem."""

    def _agora(self) -> datetime:
        return timezone.make_aware(datetime(2026, 10, 13, 12, 0))

    def test_urgencia_pelo_dia_do_inicio(self):
        agora = self._agora()
        assert linha_lista.estado_temporal(date(2026, 10, 15), None, agora,
                                           pendente=True)["urgencia"] == "perigo"
        assert linha_lista.estado_temporal(date(2026, 10, 19), None, agora,
                                           pendente=True)["urgencia"] == "aviso"
        assert linha_lista.estado_temporal(date(2026, 10, 25), None, agora,
                                           pendente=True)["urgencia"] == ""
        assert linha_lista.estado_temporal(date(2026, 10, 15), None, agora)["urgencia"] == ""

    def test_estrada_em_passos_de_dez(self):
        agora = self._agora()
        estado = linha_lista.estado_temporal(date(2026, 10, 12), date(2026, 10, 14), agora)
        assert estado["progresso"] == 50
        assert linha_lista.estado_temporal(date(2026, 10, 20), date(2026, 10, 21),
                                           agora)["progresso"] is None


@pytest.mark.parametrize("rota", ["viagens:ordens", "viagens:termos", "viagens:planos",
                                  "viagens:viagens"])
@pytest.mark.parametrize("atencao", ["", "urgentes", "vazios", "inexistente"])
def test_listas_aceitam_o_recorte_de_atencao(operador, rota, atencao):
    assert operador.get(reverse(rota), {"atencao": atencao} if atencao else {}).status_code == 200


def test_os_vazia_filtra_e_sai_de_uma_vez(operador, c):
    op = c.usuarios["operador"]
    vazia, _ = ordens.salvar(op)
    cheia, _ = ordens.salvar(op, motivo="Apoio à operação.")
    html = operador.get(reverse("viagens:ordens"), {"atencao": "vazios"}).content.decode()
    assert "atencao-lista__cartao--ativo" in html and "Excluir" in html
    assert operador.post(reverse("viagens:excluir_ordens_vazias")).status_code == 302
    assert not OrdemServico.objects.filter(pk=vazia.pk).exists()
    assert OrdemServico.objects.filter(pk=cheia.pk).exists()


def test_os_urgente_aparece_no_recorte(operador, c):
    op = c.usuarios["operador"]
    hoje = timezone.localdate()
    urgente, _ = ordens.salvar(op, data_inicio=hoje + timedelta(days=2),
                               data_fim=hoje + timedelta(days=3), motivo="Operação.")
    distante, _ = ordens.salvar(op, data_inicio=hoje + timedelta(days=30), motivo="Depois.")
    html = operador.get(reverse("viagens:ordens"), {"atencao": "urgentes"}).content.decode()
    assert urgente.numero_formatado in html and distante.numero_formatado not in html
    assert "registro--urgente-perigo" in html


def test_termo_e_plano_vazios_saem_de_uma_vez(operador, c):
    op = c.usuarios["operador"]
    termo = termos.salvar(op)
    plano, _ = planos.salvar(op)
    assert operador.post(reverse("viagens:excluir_termos_vazios")).status_code == 302
    assert operador.post(reverse("viagens:excluir_planos_vazios")).status_code == 302
    assert not TermoAutorizacao.objects.filter(pk=termo.pk).exists()
    assert not PlanoTrabalho.objects.filter(pk=plano.pk).exists()


def test_viagem_vazia_sai_e_a_preenchida_fica(operador, c):
    op = c.usuarios["operador"]
    # Na ordem: `criar` reaproveita a viagem vazia de quem cria (não deixa lixo).
    cheia = viagem.criar(op, data_inicio=timezone.localdate() + timedelta(days=10))
    vazia = viagem.criar(op)
    assert operador.get(reverse("viagens:excluir_viagens_vazias")).status_code == 405
    assert operador.post(reverse("viagens:excluir_viagens_vazias")).status_code == 302
    assert not Viagem.objects.filter(pk=vazia.pk).exists()
    assert Viagem.objects.filter(pk=cheia.pk).exists()


def test_resumo_de_cada_lista_tem_mais_acoes_e_abrir(operador, c):
    op = c.usuarios["operador"]
    ordem, _ = ordens.salvar(op, motivo="Apoio.")
    termo = termos.salvar(op, evento="Feira")
    plano, _ = planos.salvar(op)
    nova = viagem.criar(op, data_inicio=timezone.localdate() + timedelta(days=5))
    for rota, pk, abrir in [("viagens:resumo_ordem", ordem.pk, "Abrir a OS"),
                            ("viagens:resumo_termo", termo.pk, "Abrir o termo"),
                            ("viagens:resumo_plano", plano.pk, "Abrir o plano"),
                            ("viagens:resumo_viagem", nova.pk, "Abrir a viagem")]:
        html = operador.get(reverse(rota, args=[pk])).content.decode()
        assert "Mais ações" in html and abrir in html and "Conferência" in html, rota
        assert "Ver resumo" not in html  # dentro da janela, o menu não oferece a própria janela


def test_resumo_de_outra_unidade_nao_abre(client, c):
    ordem, _ = ordens.salvar(c.usuarios["operador"], motivo="Apoio.")
    client.force_login(c.usuarios["outra"])
    assert client.get(reverse("viagens:resumo_ordem", args=[ordem.pk])).status_code == 404
