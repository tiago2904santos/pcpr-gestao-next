"""CB5c: o protocolo de pagamento — a lista do anexo na ordem (pronto ou o que falta), os
arquivos (ZIP ou PDF único, o que falta fica de fora), o atesto registrado ao baixar (uma
vez, com protocolo) e os textos do eProtocolo."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import pedidos, protocolo
from gestao.coffee.models import Certidao, Contrato, Fornecedor, Lote, Solicitacao, TermoAditivo
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _pdf_bytes(texto: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=f"<p>{texto}</p>").write_pdf()


@pytest.fixture
def os_(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", numero_gms="4400",
                                termo_aditivo="1", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    TermoAditivo.objects.create(contrato=c, numero="1")  # sem PDF
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500)
    lote.municipios.set([curitiba])
    s = pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Posse", "quantidade": 40}).solicitacao
    Solicitacao.objects.filter(pk=s.pk).update(
        local_entrega="Auditório", responsavel="Plantão", nota_fiscal="8957",
        numero_oficio=f"7/{hoje.year}", protocolo_pagamento="12.345.678-9")
    s.refresh_from_db()
    s.nota_pdf.save("nota.pdf", ContentFile(_pdf_bytes("Nota 8957")), save=True)
    Certidao.objects.create(fornecedor=f, tipo="fgts", validade=hoje - timedelta(days=1),
                            enviada_por=u, arquivo=ContentFile(_pdf_bytes("CRF"), name="f.pdf"))
    return u, s


def test_lista_do_anexo_na_ordem(os_):
    u, s = os_
    itens = protocolo.itens(u, s)
    titulos = [i.titulo for i in itens]
    assert titulos[0].startswith("Ordem de serviço") and titulos[1].startswith("Ofício 7/")
    assert titulos[2].startswith("Nota fiscal 8957") and titulos[3].startswith("Certifico")
    assert titulos[4:9] == ["Certidão FGTS", "Certidão Trabalhista", "Certidão Municipal",
                            "Certidão Estadual (Paraná)", "Certidão Federal"]
    assert titulos[9] == "Termo aditivo 1" and titulos[10] == "Contrato 12/2025"
    fgts = itens[4]
    assert fgts.pronto and fgts.aviso.startswith("Vencida em")
    assert itens[5].falta == "Certidão não cadastrada."
    assert itens[9].falta == "Anexe o PDF do termo aditivo em Cadastros › Contratos."
    assert itens[10].falta == "Anexe o PDF no cadastro do contrato."


def test_baixar_zip_unico_e_atesto(os_):
    u, s = os_
    with pytest.raises(pedidos.PedidoInvalido, match="Marque ao menos um arquivo"):
        protocolo.baixar(u, s.pk, [])
    pacote = protocolo.baixar(u, s.pk, ["os", "oficio", "notas", "contrato"])
    assert pacote.tipo == "application/zip"
    nomes = zipfile.ZipFile(io.BytesIO(pacote.conteudo)).namelist()
    assert [n[:2] for n in nomes] == ["01", "02", "03", "04"]
    s.refresh_from_db()
    assert s.atesto_em == timezone.localdate()  # baixar registra o atesto
    unico = protocolo.baixar(u, s.pk, ["os", "notas"], "unico")
    from pypdf import PdfReader
    assert unico.tipo == "application/pdf" and len(PdfReader(io.BytesIO(unico.conteudo)).pages) >= 3
    Solicitacao.objects.filter(pk=s.pk).update(atesto_em=date(2026, 1, 2))
    protocolo.baixar(u, s.pk, ["oficio"])
    s.refresh_from_db()
    assert s.atesto_em == date(2026, 1, 2)  # uma vez só


def test_parte_sem_documento_e_textos(os_):
    u, s = os_
    Certidao.objects.all().delete()
    Solicitacao.objects.filter(pk=s.pk).update(nota_pdf="")
    s.refresh_from_db()
    pacote = protocolo.baixar(u, s.pk, ["notas"])  # só o certifico pronto
    assert pacote.tipo == "application/pdf"
    with pytest.raises(pedidos.PedidoInvalido, match="nenhum documento disponível ainda"):
        protocolo.baixar(u, s.pk, ["contrato"])
    textos = {k: t for k, _r, t in protocolo.textos(s)}
    assert textos["detalhamento"] == "ENVIO P/ PAGAMENTO DA NOTA FISCAL N 8957 - (BUFFET EXEMPLO)"
    assert textos["assunto_despacho"] == "CONTRATO 12/2025 - GMS 4400 - TERMO ADITIVO No 1"
    assert textos["despacho"].startswith("Ao GAF,\nEncaminhamos o presente protocolado")
    assert textos["interessado"] == "11.222.333/0001-81 — Buffet Exemplo Ltda"


def test_tela_do_protocolo(os_):
    u, s = os_
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:protocolo", args=[s.pk])).content.decode()
    assert "Textos para copiar" in html and 'data-copiar-alvo="texto-detalhamento"' in html
    assert "Anexe o PDF no cadastro do contrato." in html
    r = cli.post(reverse("coffee:baixar_protocolo", args=[s.pk]),
                 {"partes": ["oficio"], "formato": "zip"})
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    r = cli.post(reverse("coffee:baixar_protocolo", args=[s.pk]), {}, follow=True)
    assert "Marque ao menos um arquivo para baixar." in r.content.decode()
