"""Baixar documentos (paridade com o modal da referência): lista, um arquivo, um PDF só, ZIP,
via assinada × original, DOCX, ordem da tela, permissões e cancelado."""

from __future__ import annotations

import io
import zipfile

import pikepdf
import pytest
from django.test import Client
from django.urls import reverse

from gestao.plataforma import outbox
from gestao.viagens import assinados, pacotes, services, termos
from gestao.viagens.models import Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _emitido(c) -> Oficio:
    while outbox.processar_lote():
        pass
    return Oficio.objects.get(pk=c.ids["oficio_emitido"])


def _assinado_valido() -> bytes:
    from weasyprint import HTML
    return HTML(string="<p>VIA ASSINADA DE TESTE</p>").write_pdf()


def test_lista_do_oficio_com_termos_e_estados(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    termo = termos.salvar(op, oficio=oficio)
    assinados.anexar(op, assinados.Alvo("oficio", oficio), nome="a.pdf",
                     conteudo=_assinado_valido())
    r = _cliente(op).get(reverse("viagens:baixar_oficio", args=[oficio.pk]))
    assert r.status_code == 200 and r["Cache-Control"] == "no-store"
    itens = r.json()["itens"]
    assert itens[0] == {"valor": "oficio", "nome": "Ofício",
                        "detalhe": f"Ofício {oficio.numero_formatado}",
                        "estado": "Assinado", "assinado": True}
    valores = [i["valor"] for i in itens]
    assert f"termo-{termo.pk}-generico" in valores
    assert "justificativa" not in valores  # sem texto de justificativa


def test_um_documento_pdf_assinado_e_original(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    via = _assinado_valido()
    assinados.anexar(op, assinados.Alvo("oficio", oficio), nome="a.pdf", conteudo=via)
    url = reverse("viagens:baixar_oficio", args=[oficio.pk])
    cli = _cliente(op)
    r = cli.post(url, {"itens": ["oficio"], "formato": "pdf", "versao": "assinado"})
    assert r.content == via and "assinado.pdf" in r["Content-Disposition"]
    assert r["Cache-Control"] == "no-store"
    r = cli.post(url, {"itens": ["oficio"], "formato": "pdf", "versao": "original"})
    doc = assinados.documento_emitido(oficio, "oficio")
    with doc.arquivo.open("rb") as f:
        assert r.content == f.read()


def test_pdf_unico_na_ordem_da_tela_e_zip_com_nomes(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    termo = termos.salvar(op, oficio=oficio)
    url = reverse("viagens:baixar_oficio", args=[oficio.pk])
    escolhidos = [f"termo-{termo.pk}-generico", "oficio"]  # pedido fora de ordem
    cli = _cliente(op)
    r = cli.post(url, {"itens": escolhidos, "formato": "pdf", "saida": "unico"})
    assert r["Content-Type"] == "application/pdf"
    assert f'oficio-{oficio.numero:02d}-{oficio.ano}-documentos.pdf' in r["Content-Disposition"]
    with pikepdf.open(io.BytesIO(r.content)) as pdf:
        assert len(pdf.pages) >= 2
    r = cli.post(url, {"itens": escolhidos, "formato": "docx", "saida": "unico"})
    assert r["Content-Type"] == "application/zip"  # DOCX com "um só" vira ZIP
    nomes = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert nomes[0].startswith("oficio-") and nomes[0].endswith(".docx")  # ordem da tela
    assert nomes[1] == f"termo-{termo.pk}-generico.docx"


def test_rascunho_sai_como_minuta_e_nao_emite(c):
    rascunho = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    r = _cliente(c.usuarios["operador"]).post(
        reverse("viagens:baixar_oficio", args=[rascunho.pk]),
        {"itens": ["oficio"], "formato": "pdf"})
    assert r.content.startswith(b"%PDF") and "minuta-oficio" in r["Content-Disposition"]
    rascunho.refresh_from_db()
    assert rascunho.situacao == Oficio.Situacao.RASCUNHO and not rascunho.documentos.exists()


def test_nada_marcado_item_desconhecido_e_formato(c):
    oficio = _emitido(c)
    cli = _cliente(c.usuarios["operador"])
    url = reverse("viagens:baixar_oficio", args=[oficio.pk])
    r = cli.post(url, {"formato": "pdf", "voltar": "/viagens/"}, follow=True)
    assert "Marque ao menos um documento para baixar." in r.content.decode()
    assert cli.post(url, {"itens": ["nao-existe"], "formato": "pdf"}).status_code == 404
    assert cli.post(url, {"itens": ["oficio"], "formato": "odt"}).status_code == 404


def test_permissoes_e_cancelado(c):
    oficio = _emitido(c)
    url = reverse("viagens:baixar_oficio", args=[oficio.pk])
    assert _cliente(c.usuarios["outra"]).get(url).status_code == 404
    assert _cliente(c.usuarios["consulta"]).get(url).status_code == 403
    cancelado = Oficio.objects.get(pk=c.ids["oficio_cancelado"])
    r = _cliente(c.usuarios["operador"]).post(
        reverse("viagens:baixar_oficio", args=[cancelado.pk]),
        {"itens": ["oficio"], "formato": "pdf"}, follow=True)
    assert "Reative o ofício antes de baixar documentos." in r.content.decode()


def test_termo_e_justificativa(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    termo = termos.salvar(op, oficio=oficio)
    cli = _cliente(op)
    itens = cli.get(reverse("viagens:baixar_termo", args=[termo.pk])).json()["itens"]
    assert itens[-1]["valor"] in ("generico", "viatura")
    r = cli.post(reverse("viagens:baixar_termo", args=[termo.pk]),
                 {"itens": [i["valor"] for i in itens], "formato": "pdf"})
    assert r["Content-Type"] == "application/zip"
    assert f"termo-{termo.pk}-documentos.zip" in r["Content-Disposition"]
    termos.cancelar(op, termo.pk, "Adiado")
    r = cli.get(reverse("viagens:baixar_termo", args=[termo.pk]), follow=True)
    assert "Reative o termo antes de baixar documentos." in r.content.decode()
    # Justificativa: ela primeiro, depois o ofício.
    rascunho = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    services.salvar_dados(rascunho, op, {"justificativa": "Convite recebido em cima da hora."})
    itens = cli.get(reverse("viagens:baixar_justificativa", args=[rascunho.pk])).json()["itens"]
    assert [i["valor"] for i in itens] == ["justificativa", "oficio"]


def test_nomes_repetidos_no_zip_ganham_numero():
    assert pacotes._unicos(["a.pdf", "a.pdf", "b.pdf", "a.pdf"]) == [
        "a.pdf", "a (2).pdf", "b.pdf", "a (3).pdf"]


def test_via_que_nao_abre_nao_junta_e_avisa(c):
    oficio = _emitido(c)
    op = c.usuarios["operador"]
    termo = termos.salvar(op, oficio=oficio)
    assinados.anexar(op, assinados.Alvo("oficio", oficio), nome="a.pdf",
                     conteudo=b"%PDF-1.4\nquebrado")
    r = _cliente(op).post(reverse("viagens:baixar_oficio", args=[oficio.pk]),
                          {"itens": ["oficio", f"termo-{termo.pk}-generico"], "formato": "pdf",
                           "saida": "unico", "voltar": "/viagens/"}, follow=True)
    assert "baixe em arquivos separados" in r.content.decode()
