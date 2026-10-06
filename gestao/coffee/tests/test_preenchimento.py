"""CB7c: "Preencher com um e-mail" — sugestões no formulário, avisos de lote/saldo e de
período, OS já criadas do mesmo e-mail; e os locais de entrega já usados."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import preenchimento
from gestao.coffee.models import Contrato, Fornecedor, Lote, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    cwb = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                          defaults={"nome": "Curitiba", "uf": "PR"})[0]
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=40)
    lote.municipios.set([cwb])
    data = hoje + timedelta(days=12)
    email = (f"Assunto: Coffee para o seminário de inteligência\nBom dia,\npedimos coffee "
             f"break dia {data:%d/%m/%Y} às 10h no Auditório Central, em Curitiba, para 60 "
             "pessoas.\nRecebe: Agente João\n")
    return u, hoje, data, email


def test_sugestoes_e_avisos(cenario):
    u, hoje, data, email = cenario
    s = preenchimento.sugerir(u, email, hoje)
    assert s.iniciais["municipio"] == "Curitiba/PR" and s.iniciais["data_evento"] == data
    assert s.iniciais["quantidade"] == 60 and s.iniciais["local_entrega"] == "Auditório Central"
    assert s.iniciais["descricao"] == "Coffee para o seminário de inteligência - Curitiba"
    assert "numero" not in s.iniciais  # o nº da OS nunca é sugerido
    assert len(s.avisos) == 1 and s.avisos[0].startswith("O Lote 1 (")
    assert ("que atende Curitiba, tem saldo de 40 unidade(s) e o pedido é de 60: a "
            "solicitação não poderá ser salva com essa quantidade.") in s.avisos[0]
    periodo = preenchimento.sugerir(u, "coffee de 20 a 22/10 em Curitiba, 10 pessoas", hoje)
    assert any("e a OS tem uma data só: preenchi o primeiro dia" in a for a in periodo.avisos)
    assert preenchimento.sugerir(u, "obrigado", hoje).avisos == [preenchimento.MSG_VAZIO]


def test_tela_preenche_registra_e_lembra_o_email(cenario):
    u, hoje, data, email = cenario
    email = email.replace("60 pessoas", "30 pessoas")
    cli = Client()
    cli.force_login(u)
    html = cli.post(reverse("coffee:preencher"), {"email": email}).content.decode()
    assert "Lido do e-mail" in html and 'value="Curitiba/PR"' in html and 'value="30"' in html
    digital = preenchimento.dominio_email.impressao(email)
    assert f'value="{digital}"' in html
    r = cli.post(reverse("coffee:nova"), {
        "municipio": "Curitiba/PR", "data_solicitacao": f"{hoje:%d/%m/%Y}", "numero": "",
        "descricao": "Seminário de inteligência", "quantidade": "30",
        "data_evento": f"{data:%d/%m/%Y}", "local_entrega": "Auditório Central",
        "email_impressao": digital})
    assert r.status_code == 302
    s = Solicitacao.objects.get()
    assert s.email_impressao == digital
    assert "Preenchida a partir de um e-mail." in s.movimentos.get().texto
    html = cli.post(reverse("coffee:preencher"), {"email": email}).content.decode()
    assert "Já há solicitação criada a partir deste e-mail" in html
    nova = cli.get(reverse("coffee:nova")).content.decode()
    assert '<option value="Auditório Central">' in nova and 'list="locais-usados"' in nova
    cli.force_login(Usuario.objects.create_user("beto", "b@teste.invalid", None, nome="Beto"))
    assert cli.post(reverse("coffee:preencher"), {"email": email}).status_code == 403
