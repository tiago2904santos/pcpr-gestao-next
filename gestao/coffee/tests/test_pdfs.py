"""CB5b: PDF da nota fiscal (número sugerido pelo texto, valores para conferir, avisos) e da
ordem bancária (exige nota; data lida entra quando é o próximo marco; vale para o pagamento
conjunto; aviso do valor). PDFs gerados no próprio teste."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import conjunto, pdfs, pedidos
from gestao.coffee.models import Contrato, Fornecedor, Lote, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db
CHAVE = "41260911222333000181550010000089571000000017"


def _pdf(texto: str, nome: str = "doc.pdf") -> SimpleUploadedFile:
    from weasyprint import HTML
    return SimpleUploadedFile(nome, HTML(string=f"<p>{texto}</p>").write_pdf(),
                              content_type="application/pdf")


@pytest.fixture
def os_(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="1/2026", valor_unitario=Decimal("21.07"),
                                vigencia_fim=hoje + timedelta(days=300))
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500)
    lote.municipios.set([curitiba])
    s = pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Evento", "quantidade": 40,
                           "data_evento": hoje + timedelta(days=3)}).solicitacao
    return u, s


def test_nota_le_o_numero_e_confere(os_):
    u, s = os_
    texto = (f"DANFE CHAVE DE ACESSO {CHAVE} DATA DA EMISSÃO 01/01/2020 "
             "VALOR TOTAL DA NOTA 900,00")
    r = pdfs.anexar_nota(u, s.pk, _pdf(texto))
    s.refresh_from_db()
    assert r.mensagem == "Nota fiscal 8957 anexada — o número foi lido do PDF."
    assert s.nota_fiscal == "8957" and s.nota_valor == Decimal("900.00")
    avisos = pdfs.avisos_da_nota(s)
    assert any("não bate com 40 pessoas × R$ 21,07 = R$ 842,80" in a for a in avisos)
    assert any("antes do evento" in a for a in avisos)
    r = pdfs.anexar_nota(u, s.pk, _pdf("um PDF sem número"))
    assert r.aviso and "não deu para ler o número" in r.mensagem
    s.refresh_from_db()
    assert s.nota_fiscal == "8957"  # o digitado/lido antes fica
    pdfs.remover_nota(u, s.pk)
    s.refresh_from_db()
    assert not s.nota_pdf and s.nota_valor is None


def test_ob_exige_nota_e_entra_como_proximo_marco(os_):
    u, s = os_
    texto_ob = "Ordem Bancária 2026OB012345 Data de Emissão 10/03/2026 Valor 842,80"
    with pytest.raises(pedidos.PedidoInvalido, match="Registre a nota fiscal antes"):
        pdfs.anexar_ob(u, s.pk, _pdf(texto_ob))
    Solicitacao.objects.filter(pk=s.pk).update(nota_fiscal="1",
                                               protocolo_pagamento="12.345.678-9")
    r = pdfs.anexar_ob(u, s.pk, _pdf(texto_ob))
    assert "registre o atesto para a data da OB entrar" in r.mensagem and r.aviso
    Solicitacao.objects.filter(pk=s.pk).update(atesto_em=date(2026, 3, 5))
    r = pdfs.anexar_ob(u, s.pk, _pdf(texto_ob))
    s.refresh_from_db()
    assert s.ordem_bancaria_em == date(2026, 3, 10) and s.ob_numero == "2026OB012345"
    assert "OB emitida em 10/03/2026 (data lida do PDF)" in r.mensagem
    assert pdfs.aviso_da_ob(s) == ""  # 40 × 21,07 = 842,80


def test_ob_vale_para_o_pagamento_conjunto(os_):
    u, a = os_
    b = pedidos.salvar(u, {"municipio": a.municipio, "data_solicitacao": a.data_solicitacao,
                           "numero": "", "descricao": "Outro", "quantidade": 10}).solicitacao
    conjunto.definir(u, a.pk, [b.pk])
    Solicitacao.objects.filter(pk__in=[a.pk, b.pk]).update(nota_fiscal="1")
    pdfs.anexar_ob(u, a.pk, _pdf("2026OB000001 Valor 100,00"))
    b.refresh_from_db()
    assert b.ob_numero == "2026OB000001" and b.ob_pdf.name == Solicitacao.objects.get(
        pk=a.pk).ob_pdf.name
    assert "não bate com o valor das notas" in pdfs.aviso_da_ob(Solicitacao.objects.get(pk=a.pk))
    pdfs.remover_ob(u, b.pk)
    assert not Solicitacao.objects.filter(pk__in=[a.pk, b.pk]).exclude(ob_pdf="").exists()


def test_telas_dos_pdfs(os_):
    u, s = os_
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Nota fiscal e ordem bancária em PDF" in html
    r = cli.post(reverse("coffee:anexar_pdf", args=[s.pk, "nota"]),
                 {"arquivo": _pdf(f"CHAVE {CHAVE} VALOR TOTAL DA NOTA 842,80")}, follow=True)
    assert "Nota fiscal 8957 anexada" in r.content.decode()
    r = cli.get(reverse("coffee:baixar_pdf", args=[s.pk, "nota"]))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert cli.get(reverse("coffee:baixar_pdf", args=[s.pk, "ob"])).status_code == 404
    assert cli.post(reverse("coffee:anexar_pdf", args=[s.pk, "outro"])).status_code == 404
