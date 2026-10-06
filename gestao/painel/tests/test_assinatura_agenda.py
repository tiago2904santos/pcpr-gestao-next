"""A2c: a assinatura ICS da agenda — o link aparece uma vez (só o hash fica no banco), o
feed público só responde ao token válido de conta ativa e de antes da troca de senha (404
seco), leva só o título externo da fonte, o período e a situação (nada de texto livre ou
nomes), gerar de novo invalida o anterior, revogar desliga e o token não vai para o log."""

from __future__ import annotations

import logging
import re
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma import ics
from gestao.plataforma.agenda import Compromisso
from gestao.plataforma.logs import MascararSegredos
from gestao.plataforma.models import AssinaturaAgenda
from gestao.viagens import viagem
from gestao.viagens.models import Viagem
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db


def test_formato_rfc5545_sem_texto_livre():
    assert ics.escapar("a;b,c\nd") == "a\\;b\\,c\\nd"
    assert ics.escapar("x\rURL:y\x07") == "x\\nURL:y"  # CR solto e controles não quebram linha
    linhas = ics.dobrar("X" * 160)
    assert all(len(linha.encode()) <= 75 for linha in linhas)
    assert all(linha.startswith(" ") for linha in linhas[1:])
    c = Compromisso(fonte="viagem", chave="viagem-1", titulo="Feira — Operação reservada",
                    inicio=date(2026, 10, 7), fim=date(2026, 10, 8), url="/viagens/1/",
                    encerrado=True, situacao="Cancelada", detalhes=(("Motivo", "segredo"),))
    texto = ics.montar([c], {"viagem": "Viagens"}, base_url="https://x.invalid",
                       dominio="x.invalid", agora=timezone.now())
    assert "\r\nSUMMARY:Viagens\r\n" in texto  # o rótulo da fonte, não o título da tela
    assert "Operação reservada" not in texto and "segredo" not in texto
    assert "DTSTART;VALUE=DATE:20261007" in texto and "DTEND;VALUE=DATE:20261009" in texto
    assert "STATUS:CANCELLED" in texto and "URL:https://x.invalid/viagens/1/" in texto
    externo = Compromisso(fonte="viagem", chave="v-2", titulo="x", inicio=date(2026, 10, 7),
                          titulo_externo="Viagem, PCPR")
    assert "SUMMARY:Viagem\\, PCPR" in ics.montar([externo], {}, base_url="", dominio="d",
                                                   agora=timezone.now())


def test_log_sem_token():
    registro = logging.LogRecord("django.request", logging.WARNING, __file__, 1,
                                 "Not Found: %s", ("/agenda/ics/abc123SEGREDO.ics",), None)
    MascararSegredos().filter(registro)
    assert "SEGREDO" not in registro.getMessage() and "[token]" in registro.getMessage()


def _link(html: str) -> str:
    m = re.search(r'value="(https?://[^"]+/agenda/ics/[^"]+\.ics)"', html)
    assert m, "link não apareceu"
    return "/" + m.group(1).split("://", 1)[1].split("/", 1)[1]


def test_gerar_usar_trocar_revogar():
    c = cenario_completo()
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    Viagem.objects.filter(pk=v.pk).update(data_inicio=timezone.localdate(), titulo="Feira",
                                          motivo="Motivo reservado (teste)")
    cli = Client()
    cli.force_login(op)
    r = cli.post(reverse("painel:assinar_agenda"), {"acao": "gerar"}, follow=True)
    assert r["Cache-Control"] == "no-store"
    caminho = _link(r.content.decode())
    token = caminho.rsplit("/", 1)[1].removesuffix(".ics")
    assert not AssinaturaAgenda.objects.filter(token_hash=token).exists()  # só o hash
    assert "Copie o link agora" not in cli.get(reverse("painel:agenda")).content.decode()
    anonimo = Client()
    r = anonimo.get(caminho)
    assert r.status_code == 200 and r["Content-Type"].startswith("text/calendar")
    texto = r.content.decode()
    assert "BEGIN:VCALENDAR" in texto and f"UID:viagem-{v.pk}@" in texto
    assert "Motivo reservado" not in texto and "Feira" not in texto  # nada de texto livre
    assert AssinaturaAgenda.objects.get(usuario=op).usada_em is not None
    assert anonimo.get("/agenda/ics/token-falso.ics").status_code == 404
    # Gerar de novo invalida o anterior.
    novo = _link(cli.post(reverse("painel:assinar_agenda"), {"acao": "gerar"},
                          follow=True).content.decode())
    assert anonimo.get(caminho).status_code == 404 and anonimo.get(novo).status_code == 200
    # Conta desativada não recebe.
    type(op).objects.filter(pk=op.pk).update(is_active=False)
    assert anonimo.get(novo).status_code == 404
    type(op).objects.filter(pk=op.pk).update(is_active=True)
    # Trocou a senha: o link cai.
    op = type(op).objects.get(pk=op.pk)
    op.set_password("outra-senha-local-456")
    op.save()
    assert anonimo.get(novo).status_code == 404
    cli.force_login(op)
    ultimo = _link(cli.post(reverse("painel:assinar_agenda"), {"acao": "gerar"},
                            follow=True).content.decode())
    cli.post(reverse("painel:assinar_agenda"), {"acao": "revogar"})
    assert anonimo.get(ultimo).status_code == 404 and not AssinaturaAgenda.objects.exists()
