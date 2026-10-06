"""CB5a: certidões — anexo com PDF de verdade (texto lido pelo pypdf): tipo, CNPJ e validade
conferidos; imagem vale a data informada; o quadro por fornecedor com lote ativo e as
telas. Os PDFs são gerados no próprio teste (WeasyPrint)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.coffee import certidoes, pedidos
from gestao.coffee.models import Certidao, Contrato, Fornecedor, Lote
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _pdf(texto: str, nome: str = "certidao.pdf") -> SimpleUploadedFile:
    from weasyprint import HTML
    conteudo = HTML(string=f"<html><body><p>{texto}</p></body></html>").write_pdf()
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


@pytest.fixture
def base(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    f = Fornecedor.objects.create(razao_social="Buffet Teste Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="1/2026", valor_unitario=Decimal("20"))
    Lote.objects.create(contrato=c, numero=1, exercicio="2026", quantidade_total=10)
    return u, f


def test_anexa_conferindo_tipo_cnpj_e_validade(base):
    u, f = base
    validade = timezone.localdate() + timedelta(days=120)
    texto = (f"CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS CNPJ 11.222.333/0001-81 "
             f"Válida até {validade:%d/%m/%Y}")
    c = certidoes.anexar(u, f.pk, "trabalhista", _pdf(texto))
    assert c.validade == validade and c.aviso == ""
    with pytest.raises(pedidos.PedidoInvalido,
                       match="Certidão FGTS: Este PDF parece ser a certidão Trabalhista"):
        certidoes.anexar(u, f.pk, "fgts", _pdf(texto))
    outro = texto.replace("11.222.333/0001-81", "44.555.666/0001-72")
    with pytest.raises(pedidos.PedidoInvalido, match="Esta certidão não é de Buffet Teste"):
        certidoes.anexar(u, f.pk, "trabalhista", _pdf(outro))
    with pytest.raises(pedidos.PedidoInvalido, match="Envie o arquivo em PDF"):
        certidoes.anexar(u, f.pk, "fgts", SimpleUploadedFile("x.pdf", b"nada"))


def test_imagem_vale_a_data_informada_e_quadro(base):
    u, f = base
    imagem = _pdf("")  # sem texto
    with pytest.raises(pedidos.PedidoInvalido, match="parece uma imagem"):
        certidoes.anexar(u, f.pk, "municipal", imagem)
    c = certidoes.anexar(u, f.pk, "municipal", _pdf(""), date(2020, 1, 1))
    texto, aviso = certidoes.mensagem(c)
    assert "vencida em 01/01/2020" in texto and aviso
    linhas = {linha.tipo: linha for linha in certidoes.quadro(f)}
    assert linhas["municipal"].situacao == "vencida" and linhas["federal"].situacao == "faltando"
    assert linhas["federal"].portal.startswith("https://") and linhas["municipal"].portal == ""
    hoje = timezone.localdate()
    Certidao.objects.create(fornecedor=f, tipo="municipal", arquivo=c.arquivo.name,
                            validade=hoje + timedelta(days=10), enviada_por=u)
    assert {x.tipo: x for x in certidoes.quadro(f)}["municipal"].situacao == "vencendo"


def test_telas_das_certidoes(base):
    u, f = base
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:certidoes")).content.decode()
    assert "Buffet Teste Ltda" in html and "Faltando" in html
    html = cli.get(reverse("coffee:certidoes"), {"anexar": f"{f.pk}:fgts"}).content.decode()
    assert "data-abrir-ao-carregar" in html and "Certidão FGTS" in html
    validade = timezone.localdate() + timedelta(days=60)
    r = cli.post(reverse("coffee:anexar_certidao"), {
        "fornecedor": f.pk, "tipo": "fgts", "arquivo": _pdf(
            f"Certificado de Regularidade do FGTS - CRF CNPJ 11.222.333/0001-81 "
            f"Validade: {timezone.localdate():%d/%m/%Y} a {validade:%d/%m/%Y}")}, follow=True)
    assert "conferida e anexada" in r.content.decode()
    c = Certidao.objects.get(tipo="fgts")
    assert c.validade == validade
    r = cli.get(reverse("coffee:arquivo_certidao", args=[c.pk]))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    estranho = Usuario.objects.create_user("bia", "bia@teste.invalid", None, nome="Bia")
    cli.force_login(estranho)
    assert cli.get(reverse("coffee:certidoes")).status_code == 403
