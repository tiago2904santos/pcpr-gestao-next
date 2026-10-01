"""Salvaguardas de ambiente, comandos de operação e utilitários de template."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import override_settings

from gestao.plataforma import ambiente, outbox
from gestao.plataforma.checks import verificar_ambiente
from gestao.plataforma.templatetags.ui import formatar_moeda, icone, pluralizar


@pytest.mark.parametrize("env", ["lab", "dev", "test"])
def test_operacao_destrutiva_permitida(env):
    with override_settings(APP_ENV=env):
        ambiente.exigir_ambiente_destrutivo("x")


@pytest.mark.parametrize("env", ["staging", "production"])
def test_operacao_destrutiva_bloqueada(env):
    with override_settings(APP_ENV=env), pytest.raises(ambiente.OperacaoBloqueadaPorAmbiente):
        ambiente.exigir_ambiente_destrutivo("semear_dev")


def test_check_de_deploy_recusa_configuracao_perigosa():
    with override_settings(APP_ENV="production", DEBUG=True, SECRET_KEY="dev-insecure-x"):
        ids = {e.id for e in verificar_ambiente(None)}
    assert ids == {"plataforma.E002", "plataforma.E003"}
    with override_settings(APP_ENV="marte"):
        assert [e.id for e in verificar_ambiente(None)] == ["plataforma.E001"]


@pytest.mark.django_db(transaction=True)
def test_semear_dev_bloqueado_em_producao():
    with override_settings(APP_ENV="production"), pytest.raises(
            ambiente.OperacaoBloqueadaPorAmbiente):
        call_command("semear_dev")


@pytest.mark.django_db(transaction=True)
def test_comandos_de_operacao(capsys):
    @outbox.assinante("teste.cmd")
    def _ok(payload):
        return None

    with transaction.atomic():
        outbox.publicar("teste.cmd", {}, chave="cmd-1")
    call_command("processar_outbox", "--uma-vez")
    call_command("verificar_auditoria")
    call_command("doctor")
    saida = capsys.readouterr().out
    assert "1 mensagem(ns) tratada(s)" in saida
    assert "Cadeia íntegra" in saida and "Ambiente saudável" in saida


@pytest.mark.django_db(transaction=True)
def test_verificar_auditoria_falha_se_adulterada(trilha_descartavel):
    from django.db import connection

    from gestao.identidade.models import Usuario

    Usuario.objects.create_user("z", "z@pc.pr.gov.br", "x" * 12, nome="Z")
    with connection.cursor() as cur:
        cur.execute("ALTER TABLE auditoria_evento DISABLE TRIGGER auditoria_evento_imutavel")
        cur.execute("UPDATE auditoria_evento SET operacao = 'DELETE'")
        cur.execute("ALTER TABLE auditoria_evento ENABLE TRIGGER auditoria_evento_imutavel")
    with pytest.raises(CommandError, match="QUEBRADA"):
        call_command("verificar_auditoria")


@pytest.mark.parametrize(("valor", "esperado"), [
    (Decimal("2411.56"), "R$ 2.411,56"), (0, "R$ 0,00"), (Decimal("-5.5"), "-R$ 5,50"),
    (1234567.891, "R$ 1.234.567,89"), (None, "—")])
def test_moeda(valor, esperado):
    assert formatar_moeda(valor) == esperado


def test_pluralizar_e_icone():
    assert pluralizar(1, "ofício,ofícios") == "1 ofício"
    assert pluralizar(3, "ofício,ofícios") == "3 ofícios"
    assert 'aria-hidden="true"' in icone("x")
    assert 'aria-label="Fechar"' in icone("x", rotulo="Fechar")
