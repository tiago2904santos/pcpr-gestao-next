"""I2: "Preencher com um e-mail" no atendimento à imprensa — a leitura pura (cabeçalhos,
quem pede, veículo pelo texto ou pelo domínio, contato, pedido, prazo com a hora no texto) e
a tela (as sugestões vão pela sessão para o atendimento novo; nada grava)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from gestao.identidade.models import Usuario
from gestao.imprensa import dominio_email as d
from gestao.imprensa.models import Atendimento, Veiculo

EMAIL = """De: Ana Lima <ana.lima@bandab.com.br>
Enviado em: segunda-feira, 5 de outubro de 2026 10:42
Para: Imprensa PCPR
Assunto: RE: Pedido de entrevista - operação no litoral

Bom dia! Sou Ana Lima, repórter da Banda B.
Gostaria de uma entrevista com o delegado sobre a operação de ontem. Preciso até as 17h de
hoje, pois vai ao ar no jornal da noite.
Meu telefone: (41) 99999-1234

Obrigada,
Ana"""


def test_leitura_do_email():
    leitura = d.ler(EMAIL, datetime(2026, 10, 6, 9, 0), [(1, "Banda B"), (2, "RPC")])
    assert leitura.data == date(2026, 10, 5) and leitura.horario == time(10, 42)
    assert leitura.jornalista == "Ana Lima" and leitura.veiculo_id == 1
    assert leitura.contato == "(41) 99999-1234 · ana.lima@bandab.com.br"
    assert leitura.pedido.startswith("Assunto: Pedido de entrevista - operação no litoral")
    assert "Obrigada" not in leitura.pedido  # a despedida fica fora
    assert leitura.pedido.endswith("Prazo pedido: até 17:00 de 05/10/2026.")
    assert leitura.prazo is not None and leitura.prazo.data == date(2026, 10, 5)


def test_prazo_e_veiculo_pelo_dominio():
    ref = date(2026, 10, 6)  # terça-feira
    assert d.prazo("pode mandar até amanhã às 10h?", ref).data == date(2026, 10, 7)
    assert d.prazo("a matéria vai ao ar dia 14/10", ref).data == date(2026, 10, 14)
    assert d.prazo("preciso até sexta", ref).data == date(2026, 10, 9)
    assert d.prazo("sem pressa nenhuma", ref) is None
    cab = d.cabecalhos("De: Pauta <pauta@tribunapr.com.br>\nAssunto: X")
    assert d.veiculo("texto sem veículo", cab, [(1, "RPC")]) == (None, "Tribunapr")
    assert d.veiculo("texto", d.cabecalhos("De: x <a@gmail.com>"), []) == (None, "")
    assert d.ler("ok", datetime(2026, 10, 6, 9), []).vazia


@pytest.mark.django_db
def test_tela_leva_as_sugestoes_ao_novo_atendimento():
    u = Usuario.objects.create_user("ascom", "ascom@teste.invalid", None, nome="Ascom")
    u.groups.add(Group.objects.get(name="ASCOM_IMPRENSA"))
    banda = Veiculo.objects.create(nome="Banda B")
    cli = Client()
    cli.force_login(u)
    assert "Preencher com um e-mail" in cli.get(reverse("imprensa:lista")).content.decode()
    r = cli.post(reverse("imprensa:preencher"), {"email": EMAIL})
    assert r.status_code == 302 and r["Location"] == reverse("imprensa:novo") + "?de_email=1"
    assert "ana.lima" not in r["Location"]  # nada do e-mail na URL
    html = cli.get(r["Location"]).content.decode()
    assert 'value="Ana Lima"' in html and "Lido do e-mail" in html
    assert f'<option value="{banda.pk}" selected' in html
    assert "operação no litoral" in html
    assert not Atendimento.objects.exists()  # nada gravado
    r = cli.post(reverse("imprensa:preencher"), {"email": "obrigado"})
    assert r.status_code == 422 and "Não deu para ler nada" in r.content.decode()
    leitor = Usuario.objects.create_user("zeca", "z@teste.invalid", None, nome="Zeca")
    cli.force_login(leitor)
    assert cli.get(reverse("imprensa:preencher")).status_code == 403
