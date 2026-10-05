"""Carimbo do número de solicitação no ofício assinado (módulo 9d-3): posição por servidor
(página e frações), validações, o número desenhado na prévia e no pacote sem alterar a via,
a pendência da referência, trava e permissões."""

from __future__ import annotations

import io

import pytest
from django.test import Client
from django.urls import reverse
from pypdf import PdfReader

from gestao.plataforma import outbox
from gestao.viagens import assinados, carimbo, prestacao
from gestao.viagens.models import Oficio, PrestacaoContas, ViaAssinada

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    cen = cenario_completo()
    while outbox.processar_lote():  # o PDF do ofício emitido
        pass
    return cen


def _com_via(c):
    p = PrestacaoContas.objects.select_related("oficio").get(oficio_id=c.ids["oficio_emitido"])
    oficio = Oficio.objects.get(pk=p.oficio_id)
    doc = assinados.documento_emitido(oficio, "oficio")
    with doc.arquivo.open("rb") as f:
        assinados.anexar(c.usuarios["operador"], assinados.Alvo(ViaAssinada.Tipo.OFICIO, oficio),
                         nome="oficio-assinado.pdf", conteudo=f.read())
    a, b = prestacao.ativos().filter(prestacao=p).order_by("servidor__nome")
    prestacao.salvar_solicitacao(c.usuarios["operador"], a.pk, numero="2030/4242",
                                 liberacao=None, prazo=None)
    a.refresh_from_db()
    return p, a, b


def _texto(pdf: bytes) -> str:
    return "".join(pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(pdf)).pages)


def test_pendencia_e_posicao(c):
    p, a, b = _com_via(c)
    assert carimbo.PENDENCIA in prestacao.pendencias(a)
    assert carimbo.PENDENCIA not in prestacao.pendencias(b)  # sem número, não cobra
    carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=0, x=0.7, y=0.4)
    assert carimbo.PENDENCIA not in prestacao.pendencias(a)
    carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=0, x=0.6, y=0.5)  # atualiza
    assert carimbo.carimbos(carimbo.via_do_oficio(p))[0].x == 0.6
    with pytest.raises(carimbo.CarimboInvalido, match="dentro da página"):
        carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=0, x=1.5, y=0.4)
    with pytest.raises(carimbo.CarimboInvalido, match="página"):
        carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=99, x=0.5, y=0.4)


def test_numero_desenhado_sem_alterar_a_via(c):
    p, a, _ = _com_via(c)
    via = carimbo.via_do_oficio(p)
    with via.arquivo.open("rb") as f:
        original = f.read()
    assert "2030/4242" not in _texto(original)
    carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=0, x=0.7, y=0.4)
    assert "2030/4242" in _texto(carimbo.carimbado(via))
    with via.arquivo.open("rb") as f:
        assert f.read() == original  # o arquivo assinado não muda
    # O número sai sempre do cadastro atual.
    prestacao.salvar_solicitacao(c.usuarios["operador"], a.pk, numero="2030/9999",
                                 liberacao=None, prazo=None)
    assert "2030/9999" in _texto(carimbo.carimbado(via))


def test_tela_previa_trava_e_permissoes(c):
    p, a, _ = _com_via(c)
    op, outra = Client(), Client()
    op.force_login(c.usuarios["operador"])
    outra.force_login(c.usuarios["outra"])
    html = op.get(reverse("viagens:documentos_prestacao", args=[p.pk])).content.decode()
    assert "Número da solicitação no ofício assinado" in html and "sem posição" in html
    r = op.post(reverse("viagens:carimbar_numero", args=[a.pk]),
                {"pagina": "1", "x": "70", "y": "40,5"})
    assert r["Location"].endswith("#oficio_assinado")
    assert carimbo.carimbos(carimbo.via_do_oficio(p))[0].y == pytest.approx(0.405)
    r = op.post(reverse("viagens:carimbar_numero", args=[a.pk]),
                {"pagina": "1", "x": "abc", "y": "40"}, follow=True)
    assert "informe um número de 0 a 100" in r.content.decode()
    r = op.get(reverse("viagens:previa_carimbo", args=[p.pk]))
    assert r["Content-Type"] == "application/pdf" and "2030/4242" in _texto(r.content)
    assert outra.get(reverse("viagens:previa_carimbo", args=[p.pk])).status_code == 404
    assert outra.post(reverse("viagens:carimbar_numero", args=[a.pk])).status_code == 404
    prestacao.finalizar(c.usuarios["operador"], a.pk, "Teste da trava.")
    with pytest.raises(carimbo.CarimboInvalido, match="reabra"):
        carimbo.posicionar(c.usuarios["operador"], a.pk, pagina=0, x=0.5, y=0.5)
