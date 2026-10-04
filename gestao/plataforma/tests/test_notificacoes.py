"""Notificações (o sino): serviço, contador, central, abrir, marcar lidas e e-mail pela
outbox (paridade com core/notificacoes.py da referência)."""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from gestao.plataforma import notificacoes, outbox
from gestao.plataforma.models import MensagemOutbox, Notificacao
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def test_notificar_tira_repetidos_inativos_e_o_autor(c):
    op, gestor, outra = c.usuarios["operador"], c.usuarios["gestor"], c.usuarios["outra"]
    outra.is_active = False
    outra.save()
    criadas = notificacoes.notificar([op, op, gestor, outra], "Aviso", "Texto",
                                     "/viagens/", exceto=gestor)
    assert [n.usuario_id for n in criadas] == [op.pk]


def test_texto_longo_e_cortado_e_link_longo_some(c):
    [n] = notificacoes.notificar([c.usuarios["operador"]], "T" * 300, "M" * 400, "/" + "x" * 300)
    assert len(n.titulo) == 150 and n.titulo.endswith("…")
    assert len(n.mensagem) == 255 and n.link == ""


def test_grupo(c):
    nomes = set(notificacoes.usuarios_do_grupo("OPERADOR_VIAGENS").values_list("login",
                                                                               flat=True))
    assert {"operador", "outra"} <= nomes


def test_sino_central_abrir_e_marcar_todas(c):
    op = c.usuarios["operador"]
    notificacoes.notificar([op], "Primeiro aviso", "Detalhe", "/viagens/")
    notificacoes.notificar([op], "Segundo aviso")
    notificacoes.notificar([c.usuarios["gestor"]], "De outra pessoa")
    cli = _cliente(op)
    html = cli.get(reverse("painel:inicio")).content.decode()
    assert "Notificações (2 não lidas)" in html and "cabecalho__marcador" in html
    html = cli.get(reverse("painel:notificacoes")).content.decode()
    assert "Primeiro aviso" in html and "Segundo aviso" in html
    assert "De outra pessoa" not in html and "Marcar todas como lidas" in html
    primeiro = Notificacao.objects.get(titulo="Primeiro aviso")
    r = cli.get(reverse("painel:abrir_notificacao", args=[primeiro.pk]))
    assert r.status_code == 302 and r["Location"] == "/viagens/"
    primeiro.refresh_from_db()
    assert primeiro.lida
    html = cli.get(reverse("painel:notificacoes") + "?filtro=nao-lidas").content.decode()
    assert "Segundo aviso" in html and "Primeiro aviso" not in html
    cli.post(reverse("painel:marcar_notificacoes_lidas"))
    assert not Notificacao.objects.filter(usuario=op, lida=False).exists()
    html = cli.get(reverse("painel:notificacoes")).content.decode()
    assert "Marcar todas como lidas" not in html and "(2 não lidas)" not in html


def test_aviso_de_outra_pessoa_da_404_e_link_externo_e_ignorado(c):
    [alheio] = notificacoes.notificar([c.usuarios["gestor"]], "Dela")
    [externo] = notificacoes.notificar([c.usuarios["operador"]], "Externo",
                                       link="https://exemplo.invalid/")
    cli = _cliente(c.usuarios["operador"])
    assert cli.get(reverse("painel:abrir_notificacao", args=[alheio.pk])).status_code == 404
    r = cli.get(reverse("painel:abrir_notificacao", args=[externo.pk]))
    assert r["Location"] == reverse("painel:notificacoes")


def test_vazio_e_paginacao(c):
    cli = _cliente(c.usuarios["operador"])
    assert "Nenhuma notificação" in cli.get(reverse("painel:notificacoes")).content.decode()
    for i in range(30):
        notificacoes.notificar([c.usuarios["operador"]], f"Aviso {i}")
    html = cli.get(reverse("painel:notificacoes")).content.decode()
    assert "Mostrando 1–25 de 30" in html


@override_settings(NOTIFICACOES_POR_EMAIL=True,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_email_sai_pela_outbox_depois_do_commit(c):
    notificacoes.notificar([c.usuarios["operador"], c.usuarios["gestor"]], "Com e-mail",
                           "Corpo", "/viagens/")
    assert MensagemOutbox.objects.filter(topico="plataforma.email.enviar").count() == 1
    assert not mail.outbox  # na requisição, nada é enviado
    while outbox.processar_lote():
        pass
    [enviado] = mail.outbox
    assert enviado.subject == "[PCPR] Com e-mail" and len(enviado.to) == 2
    assert "Acesse: http://localhost:8000/viagens/" in enviado.body


def test_sem_email_por_padrao(c):
    notificacoes.notificar([c.usuarios["operador"]], "Sem e-mail")
    assert not MensagemOutbox.objects.filter(topico="plataforma.email.enviar").exists()
