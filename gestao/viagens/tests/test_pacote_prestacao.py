"""Pacote final da prestação (módulo 9d-2): ordem oficial, assinados no lugar dos gerados,
imagem vira página, pendências que impedem, nome do arquivo e o ZIP da equipe."""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse
from pypdf import PdfReader

from gestao.plataforma import outbox
from gestao.viagens import anexos, pacote_prestacao, prestacao
from gestao.viagens.models import PrestacaoContas

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


def _pdf(texto: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=f"<p>{texto}</p>").write_pdf()


@pytest.fixture
def c():
    cen = cenario_completo()
    while outbox.processar_lote():  # o PDF do ofício emitido
        pass
    return cen


def _prontos(c):
    p = PrestacaoContas.objects.select_related("oficio").get(oficio_id=c.ids["oficio_emitido"])
    op = c.usuarios["operador"]
    a, b = prestacao.ativos().filter(prestacao=p).select_related("servidor").order_by(
        "servidor__nome")
    a.prestacao = b.prestacao = p
    prestacao.salvar_solicitacao(op, a.pk, numero="2030/77", liberacao=None, prazo=None)
    anexos.anexar(op, p.pk, "despacho", nome="despacho.pdf", conteudo=_pdf("Despacho"))
    anexos.anexar(op, p.pk, "comprovante", servidor_pk=a.pk, nome="c2.pdf",
                  conteudo=_pdf("Comprovante 2"), data_operacao=date(2030, 1, 9))
    anexos.anexar(op, p.pk, "comprovante", servidor_pk=a.pk, nome="foto.png",
                  conteudo=_png(), data_operacao=date(2030, 1, 8))
    a.refresh_from_db()
    return p, a, b


def _png() -> bytes:
    from PIL import Image
    saida = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(saida, format="PNG")
    return saida.getvalue()


def test_ordem_oficial_e_assinados(c):
    p, a, _ = _prontos(c)
    rotulos = [r for r, _ in pacote_prestacao.partes(a)]
    assert rotulos == ["ofício", "despacho assinado", "relatório técnico", "diário de bordo",
                       "comprovante", "comprovante"]
    # Comprovantes pela data da operação: a foto (08/01) antes do PDF (09/01), e vira página.
    partes = pacote_prestacao.partes(a)
    assert PdfReader(io.BytesIO(partes[4][1])).pages[0].mediabox.width < 100  # a imagem
    op = c.usuarios["operador"]
    anexos.anexar(op, p.pk, "rt_assinado", servidor_pk=a.pk, nome="rt.pdf",
                  conteudo=_pdf("RT assinado"))
    anexos.anexar(op, p.pk, "db_assinado", nome="db.pdf", conteudo=_pdf("DB assinado"))
    rotulos = [r for r, _ in pacote_prestacao.partes(a)]
    assert "relatório técnico assinado" in rotulos and "diário de bordo assinado" in rotulos
    conteudo = pacote_prestacao.pdf(a)
    assert len(PdfReader(io.BytesIO(conteudo)).pages) >= 6


def test_sem_numero_despacho_ou_comprovante_nao_tem_pacote(c):
    _, _, b = _prontos(c)
    falta = pacote_prestacao.pendencias_do_pacote(b)
    assert falta == ["Informe o número da solicitação deste servidor.",
                     "Anexe o comprovante de saque/transferência deste servidor."]
    with pytest.raises(pacote_prestacao.PacoteIncompleto, match="número da solicitação"):
        pacote_prestacao.partes(b)


def test_nome_do_arquivo_sem_acentos(c):
    _, a, _ = _prontos(c)
    nome = pacote_prestacao.nome_do_pdf(a)
    assert nome.startswith("Prestacao solicitacao 2030-77 Oficio ") and nome.endswith(".pdf")
    assert nome.isascii() and "Arapongas" in nome


def test_zip_da_equipe_com_pendencias(c):
    p, a, b = _prontos(c)
    conteudo, gerados = pacote_prestacao.zip_da_equipe(p)
    assert gerados == 1
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        nomes = z.namelist()
        assert pacote_prestacao.nome_do_pdf(a) in nomes and "PENDENCIAS.txt" in nomes
        assert b.servidor.nome in z.read("PENDENCIAS.txt").decode()


def test_telas_e_permissoes(c):
    p, a, b = _prontos(c)
    op, outra = Client(), Client()
    op.force_login(c.usuarios["operador"])
    outra.force_login(c.usuarios["outra"])
    r = op.get(reverse("viagens:pacote_servidor", args=[a.pk]))
    assert r["Content-Type"] == "application/pdf" and "Prestacao" in r["Content-Disposition"]
    r = op.get(reverse("viagens:pacote_servidor", args=[b.pk]), follow=True)
    assert "número da solicitação" in r.content.decode()
    r = op.get(reverse("viagens:pacote_equipe", args=[p.pk]))
    assert r["Content-Type"] == "application/zip"
    assert outra.get(reverse("viagens:pacote_servidor", args=[a.pk])).status_code == 404
    assert outra.get(reverse("viagens:pacote_equipe", args=[p.pk])).status_code == 404
    html = op.get(reverse("viagens:documentos_prestacao", args=[p.pk])).content.decode()
    assert reverse("viagens:pacote_servidor", args=[a.pk]) in html
