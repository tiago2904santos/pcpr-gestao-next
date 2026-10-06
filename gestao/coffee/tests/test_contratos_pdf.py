"""CB5d: o contrato e o termo aditivo lidos do PDF (textos fictícios no modelo dos contratos
da SESP) — a leitura pura, e o anexar que cria o fornecedor, o contrato e o lote, corrige a
vigência estimada com a do aditivo, recusa documento de outro fornecedor ou que não é
contrato, e só para o administrador do módulo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.coffee import contratos_pdf, dominio_contrato
from gestao.coffee.models import Contrato, Fornecedor, Lote, TermoAditivo
from gestao.identidade.models import Usuario

CONTRATO = """SECRETARIA DE ESTADO DA SEGURANÇA PÚBLICA
SETOR DE CONTRATOS E CONVÊNIOS – CONTRATO – Nº 0101/2024 – GMS Nº 5001/2024
CONTRATANTE: O ESTADO DO PARANÁ, inscrito no CNPJ sob n. º 76.416.932/0001-81
CONTRATADO(A): BUFFET EXEMPLO FICTICIO LTDA , CNPJ nº
11.222.333/0001-81, com sede na Rua Exemplo, 100
LOTE - 01
Item Descrição Qtd. Valor Unitário Valor Total
10.000 R$ 20,0000 R$ 200.000,00
3.2 O valor total do contrato é de R$ 200.000,00 (duzentos mil reais).
8.1 O prazo de vigência do contrato é de 1 (um) ano, podendo ser prorrogado
Inserido ao Protocolo 22.000.000-0 por Servidor Ficticio em: 29/10/2024 14:51."""

ADITIVO = """CENTRO DE CONTRATOS E CONVÊNIOS – TERMO ADITIVO Nº 0300/2025
Protocolo nº 24.000.000-0–Contrato nº 0101/2024–GMS 5001/2024–1º Termo Aditivo
CONTRATANTE: O ESTADO DO PARANÁ, inscrito no CNPJ sob n. º 76.416.932/0001-81
CONTRATADO(A): BUFFET EXEMPLO FICTICIO LTDA, CNPJ nº
11.222.333/0001-81, com sede na Rua Exemplo, 100
Fica prorrogada a vigência do contrato pelo prazo de 01 (um) ano, a partir de
31/10/2025 até 30/10/2026.
passando de R$ 200.000,00 (duzentos mil reais) para R$ 210.700,00 (duzentos e dez mil)
LOTE 01
ITEM DESCRIÇÃO QTD. VALOR UNITÁRIO VALOR REPACTUADO
TIPO: Coffee Break, 04 (quatro) tipos de 10.000 R$ 20,0000 R$ 21,07"""


def test_leitura_do_contrato_e_do_aditivo():
    c = dominio_contrato.ler(CONTRATO)
    assert (c.tipo, c.numero, c.numero_gms) == ("contrato", "0101/2024", "5001/2024")
    assert (c.cnpj, c.razao_social) == ("11222333000181", "BUFFET EXEMPLO FICTICIO LTDA")
    assert (c.numero_lote, c.quantidade, c.valor_total) == (1, 10000, Decimal("200000.00"))
    assert c.vigencia_inicio == date(2024, 10, 29) and c.vigencia_fim == date(2025, 10, 28)
    assert c.vigencia_estimada and c.da_sesp
    a = dominio_contrato.ler(ADITIVO)
    assert (a.tipo, a.termo_aditivo, a.numero) == ("aditivo", "0300/2025", "0101/2024")
    assert (a.vigencia_inicio, a.vigencia_fim) == (date(2025, 10, 31), date(2026, 10, 30))
    assert not a.vigencia_estimada
    assert a.valor_unitario == Decimal("21.07") and a.valor_total == Decimal("210700.00")
    assert dominio_contrato.ler("Um ofício qualquer, sem contrato.").tipo == ""


@pytest.fixture
def admin(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("adm", "adm@teste.invalid", None, nome="Adm")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"),
                 Group.objects.get(name="ADMINISTRADOR"))
    return u


def _anexar(cli, monkeypatch, texto):
    monkeypatch.setattr(contratos_pdf, "texto_do_pdf", lambda arquivo, paginas=3: texto)
    return cli.post(reverse("coffee:anexar_contrato"),
                    {"arquivo": SimpleUploadedFile("doc.pdf", b"%PDF-1.4 doc")}, follow=True)


@pytest.mark.django_db
def test_anexar_contrato_e_aditivo(admin, monkeypatch):
    cli = Client()
    cli.force_login(admin)
    html = _anexar(cli, monkeypatch, CONTRATO).content.decode()
    assert f"Contrato 0101/2024 ({Contrato.objects.get().fornecedor})" in html
    assert "anexado e conferido; vigente até 28/10/2025 (estimada pelo prazo; o termo aditivo " \
           "confirma); 10.000 unidades; lote 1 criado" in html
    c = Contrato.objects.get(numero="0101/2024")
    assert c.fornecedor.cnpj == "11222333000181" and c.arquivo and c.vigencia_estimada
    assert c.quantidade_contratada == 10000
    assert Lote.objects.get(contrato=c).exercicio == "2024"
    _anexar(cli, monkeypatch, ADITIVO)
    c.refresh_from_db()
    assert c.termo_aditivo == "0300/2025" and c.vigencia_fim == date(2026, 10, 30)
    assert not c.vigencia_estimada and c.valor_unitario == Decimal("21.0700")
    a = TermoAditivo.objects.get(contrato=c)
    assert a.arquivo and a.vigencia_fim == date(2026, 10, 30)
    assert Lote.objects.filter(contrato=c).count() == 1  # o lote não se repete


@pytest.mark.django_db
def test_recusas(admin, monkeypatch):
    cli = Client()
    cli.force_login(admin)
    assert "não parece ser um contrato" in _anexar(cli, monkeypatch,
                                                    "Um ofício qualquer.").content.decode()
    outro = Fornecedor.objects.create(razao_social="OUTRA EMPRESA LTDA", cnpj="44555666000172")
    Contrato.objects.create(fornecedor=outro, numero="0101/2024")
    html = _anexar(cli, monkeypatch, ADITIVO).content.decode()
    assert "está cadastrado para OUTRA EMPRESA LTDA" in html
    sem_cnpj = CONTRATO.replace("11.222.333/0001-81", "").replace("0101/2024", "0202/2024")
    assert "Não achei o CNPJ do contratado no documento do contrato 0202/2024." in _anexar(
        cli, monkeypatch, sem_cnpj).content.decode()
    operador = Usuario.objects.create_user("op", "op@teste.invalid", None, nome="Op")
    operador.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    cli.force_login(operador)
    assert _anexar(cli, monkeypatch, CONTRATO).status_code == 403
