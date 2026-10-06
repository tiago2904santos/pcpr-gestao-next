"""P2: "Preencher com um e-mail" nas publicações — a leitura pura do release (título
sugerido, em caixa alta, do assunto ou a primeira frase; unidade citada ou o remetente;
fonte de quem assina) e a tela (sugestões pela sessão para a pauta nova; nada grava)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from gestao.identidade.models import Usuario
from gestao.publicacoes import dominio_email as d
from gestao.publicacoes.models import Integrante, Publicacao, UnidadeResponsavel

RELEASE = """De: 5ª SDP Maringá <5sdp@pc.pr.gov.br>
Enviado em: 05/10/2026 14:20
Assunto: RES: Release - Polícia Civil prende suspeito de furtos em Maringá

Bom dia, segue release para divulgação.

POLÍCIA CIVIL PRENDE SUSPEITO DE FURTOS EM SÉRIE EM MARINGÁ
A 5ª SDP Maringá prendeu nesta segunda-feira um homem suspeito de furtos.

Atenciosamente,
Del. Fulano de Tal
5ª SDP Maringá"""


def test_leitura_do_release():
    leitura = d.ler(RELEASE, datetime(2026, 10, 6, 9), [(1, "5ª SDP Maringá"), (2, "DHPP")])
    assert leitura.data == date(2026, 10, 5) and leitura.inicio == time(14, 20)
    assert leitura.titulo == "POLÍCIA CIVIL PRENDE SUSPEITO DE FURTOS EM SÉRIE EM MARINGÁ"
    assert leitura.unidade_id == 1 and leitura.fonte == "Del. Fulano de Tal"


def test_titulo_sugerido_assunto_e_frase():
    assert d.titulo("Sugestão de título: Operação prende quadrilha\nTexto.", "") == (
        "Operação prende quadrilha")
    assert d.titulo("texto curto", "Release - Delegacia inaugura nova sede") == (
        "Delegacia inaugura nova sede")
    assert d.titulo("A delegacia de Toledo recebeu doação de viaturas. Mais.", "") == (
        "A delegacia de Toledo recebeu doação de viaturas")
    assert d.fonte("Texto.\nInformações: escrivão Beltrano") == "escrivão Beltrano"
    sem = d.ler("De: DP Ortigueira <dp@x.invalid>\nAssunto: Doação de cestas na cidade\n",
                datetime(2026, 10, 6, 9), [])
    assert sem.unidade_id is None and sem.unidade_texto == "DP Ortigueira"
    assert d.ler("ok", datetime(2026, 10, 6, 9), []).vazia


@pytest.mark.django_db
def test_tela_leva_as_sugestoes_para_a_pauta_nova():
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana Souza")
    u.groups.add(Group.objects.get(name="ASCOM_PUBLICACOES"))
    eu = Integrante.objects.create(nome="Ana Souza")
    unidade = UnidadeResponsavel.objects.create(nome="5ª SDP Maringá")
    cli = Client()
    cli.force_login(u)
    assert "Preencher com um e-mail" in cli.get(reverse("publicacoes:lista")).content.decode()
    r = cli.post(reverse("publicacoes:preencher"), {"email": RELEASE})
    assert r.status_code == 302 and r["Location"].endswith("?de_email=1")
    html = cli.get(r["Location"]).content.decode()
    assert "POLÍCIA CIVIL PRENDE SUSPEITO" in html and "Lido do e-mail" in html
    assert f'<option value="{unidade.pk}" selected' in html
    assert f'<option value="{eu.pk}" selected' in html and 'value="Del. Fulano de Tal"' in html
    assert not Publicacao.objects.exists()
    assert cli.post(reverse("publicacoes:preencher"), {"email": "ok"}).status_code == 422
    cli.force_login(Usuario.objects.create_user("z", "z@teste.invalid", None, nome="Z"))
    assert cli.get(reverse("publicacoes:preencher")).status_code == 403
