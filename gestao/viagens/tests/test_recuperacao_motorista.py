"""Recuperação: auditoria real por trigger, simulação, isolamento e concorrência."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, transaction

from gestao.plataforma.auditoria import contexto
from gestao.plataforma.models import EventoAuditoria
from gestao.viagens import recuperacao_motorista as recuperacao
from gestao.viagens.models import Historico, Oficio, Viajante

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario(settings):
    settings.APP_ENV = "test"
    return cenario_completo()


def _corromper(cenario, *, requisicao="autosave-defeituoso", oficio_id=None):
    oficio = Oficio.objects.get(pk=oficio_id or cenario.ids["oficio_rascunho"])
    viajante = oficio.viajantes.get(motorista=True)
    with transaction.atomic(), contexto(usuario_id=None, requisicao_id=requisicao):
        Viajante.objects.filter(pk=viajante.pk).update(motorista=False)
        Oficio.objects.filter(pk=oficio.pk).update(
            motorista_externo="servidor", motorista_externo_servidor=None)
    return oficio, viajante


def test_simulacao_mostra_prova_sem_alterar_dados_ou_trilhas(cenario):
    oficio, viajante = _corromper(cenario)
    oficio.refresh_from_db()
    versao = oficio.versao
    auditoria = EventoAuditoria.objects.count()
    historico = oficio.historico.count()
    saida = StringIO()
    call_command("recuperar_motoristas", oficio=[oficio.pk], stdout=saida)
    assert "SIMULAÇÃO" in saida.getvalue() and "restaurar viajante" in saida.getvalue()
    oficio.refresh_from_db()
    viajante.refresh_from_db()
    assert oficio.motorista_externo == "servidor" and not viajante.motorista
    assert oficio.versao == versao
    assert oficio.historico.count() == historico
    assert EventoAuditoria.objects.count() == auditoria


def test_recupera_com_prova_real_incrementa_versao_e_e_idempotente(cenario):
    oficio, viajante = _corromper(cenario)
    oficio.refresh_from_db()
    versao = oficio.versao
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.aplicado and resultado.motorista_id == viajante.pk
    assert resultado.evidencia_id and not resultado.selecao_manual
    oficio.refresh_from_db()
    viajante.refresh_from_db()
    assert oficio.motorista_externo == "" and viajante.motorista
    assert oficio.versao == versao + 1
    evento = oficio.historico.get(dados__recuperacao="motorista_externo_fantasma")
    assert evento.dados["evidencia_id"] == resultado.evidencia_id
    auditoria = EventoAuditoria.objects.count()
    assert not recuperacao.recuperar_rascunho(oficio.pk, aplicar=True).aplicavel
    assert EventoAuditoria.objects.count() == auditoria
    assert oficio.historico.filter(dados__recuperacao="motorista_externo_fantasma").count() == 1


@pytest.mark.parametrize("requisicao", [None, ""])
def test_sem_requisicao_identificada_limpa_sem_inventar_motorista(cenario, requisicao):
    oficio, viajante = _corromper(cenario, requisicao=requisicao)
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.selecao_manual and resultado.motorista_id is None
    oficio.refresh_from_db()
    viajante.refresh_from_db()
    assert oficio.motorista_externo == "" and not viajante.motorista
    assert "Selecione manualmente" in oficio.historico.first().descricao


def test_req_diferente_nao_prova_desmarcacao_espuria(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    with transaction.atomic(), contexto(usuario_id=None, requisicao_id="escolha-humana"):
        oficio.viajantes.update(motorista=False)
    with transaction.atomic(), contexto(usuario_id=None, requisicao_id="outra-requisicao"):
        Oficio.objects.filter(pk=oficio.pk).update(motorista_externo="servidor")
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.selecao_manual and resultado.evidencia_id is None


def test_alteracao_posterior_da_selecao_impede_restaurar_antiga(cenario):
    oficio, viajante = _corromper(cenario)
    # Uma decisão posterior desfaz e refaz a marca: a prova antiga deixou de valer.
    with transaction.atomic(), contexto(usuario_id=None, requisicao_id="decisao-posterior"):
        Viajante.objects.filter(pk=viajante.pk).update(motorista=True)
        Viajante.objects.filter(pk=viajante.pk).update(motorista=False)
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.selecao_manual and resultado.evidencia_id is None


def test_varias_desmarcacoes_na_mesma_requisicao_sao_ambiguas(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    viajante = oficio.viajantes.get(motorista=True)
    with transaction.atomic(), contexto(usuario_id=None, requisicao_id="req-ambigua"):
        Viajante.objects.filter(pk=viajante.pk).update(motorista=False)
        Viajante.objects.filter(pk=viajante.pk).update(motorista=True)
        Viajante.objects.filter(pk=viajante.pk).update(motorista=False)
        Oficio.objects.filter(pk=oficio.pk).update(motorista_externo="servidor")
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.selecao_manual and resultado.evidencia_id is None


def test_outra_equipe_incluida_depois_impede_usar_prova_antiga(cenario):
    oficio, viajante = _corromper(cenario)
    outro = Oficio.objects.get(pk=cenario.ids["oficio_emitido"]).viajantes.first()
    Viajante.objects.create(oficio=oficio, servidor=outro.servidor)
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    assert resultado.selecao_manual and resultado.motorista_id is None
    viajante.refresh_from_db()
    assert not viajante.motorista


def test_preserva_motorista_ja_marcado(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    viajante = oficio.viajantes.get(motorista=True)
    Oficio.objects.filter(pk=oficio.pk).update(motorista_externo="servidor")
    resultado = recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    viajante.refresh_from_db()
    assert viajante.motorista and resultado.motorista_id == viajante.pk
    assert not resultado.selecao_manual and resultado.evidencia_id is None


@pytest.mark.parametrize("estado", ["emitido", "cancelado", "arquivado", "externo_legitimo",
                                    "externo_manual"])
def test_nao_toca_estados_protegidos(cenario, estado):
    from django.utils import timezone

    oficio, viajante = _corromper(cenario)
    alteracao = {}
    if estado == "emitido":
        alteracao.update(situacao=estado, emitido_em=timezone.now())
    elif estado == "cancelado":
        alteracao.update(situacao=estado, motivo_cancelamento="Cancelamento sintético do teste",
                         cancelado_em=timezone.now(), situacao_anterior="rascunho")
    elif estado == "arquivado":
        alteracao["arquivado_em"] = timezone.now()
    elif estado == "externo_legitimo":
        alteracao["motorista_externo_servidor_id"] = viajante.servidor_id
    else:
        alteracao.update(motorista_externo="manual", motorista_externo_nome="Pessoa sintética")
    Oficio.objects.filter(pk=oficio.pk).update(**alteracao)
    oficio.refresh_from_db()
    versao = oficio.versao
    auditoria = EventoAuditoria.objects.count()
    assert not recuperacao.recuperar_rascunho(oficio.pk, aplicar=True).aplicavel
    oficio.refresh_from_db()
    assert oficio.versao == versao and EventoAuditoria.objects.count() == auditoria
    for campo, valor in alteracao.items():
        assert getattr(oficio, campo) == valor


def test_falha_no_historico_desfaz_toda_a_recuperacao(cenario, monkeypatch):
    oficio, viajante = _corromper(cenario)
    oficio.refresh_from_db()
    versao = oficio.versao
    auditoria = EventoAuditoria.objects.count()

    def falhar(**kwargs):
        raise RuntimeError("falha controlada no histórico")

    monkeypatch.setattr(Historico.objects, "create", falhar)
    with pytest.raises(RuntimeError, match="falha controlada"):
        recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
    oficio.refresh_from_db()
    viajante.refresh_from_db()
    assert oficio.motorista_externo == "servidor" and not viajante.motorista
    assert oficio.versao == versao and EventoAuditoria.objects.count() == auditoria


@pytest.mark.parametrize("app_env,nome,permitido", [
    ("test", "test_gestao", True), ("lab", "gestao_lab", True),
    ("dev", "gestao_dev", True), ("preview", "pcpr_preview", True),
    ("preview", "pcpr_demo", True), ("preview", "pcpr", False),
    ("staging", "pcpr_demo", False), ("production", "pcpr_demo", False),
])
def test_guardas_de_escrita(settings, monkeypatch, app_env, nome, permitido):
    settings.APP_ENV = app_env
    monkeypatch.setitem(connection.settings_dict, "NAME", nome)
    if permitido:
        recuperacao.exigir_ambiente_de_recuperacao()
    else:
        with pytest.raises(CommandError, match="somente leitura"):
            call_command("recuperar_motoristas", aplicar=True, stdout=StringIO())


def test_duas_recuperacoes_concorrentes_gravam_uma_unica_vez(cenario):
    oficio, viajante = _corromper(cenario)
    inicio = Barrier(2)

    def executar():
        close_old_connections()
        try:
            inicio.wait(timeout=10)
            return recuperacao.recuperar_rascunho(oficio.pk, aplicar=True)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(lambda _: executar(), range(2)))
    assert sum(r.aplicado for r in resultados) == 1
    viajante.refresh_from_db()
    assert viajante.motorista
    assert oficio.historico.filter(dados__recuperacao="motorista_externo_fantasma").count() == 1
