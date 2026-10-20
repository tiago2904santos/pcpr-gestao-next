"""Leitura dos anexos da prestação: o texto do comprovante (autorização, data, valor,
operação), do RT assinado e do diário assinado transcrito em campos; o valor conferido
com a diária do ofício e com a do RT; a tela e as abas de pendência."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from gestao.viagens import anexos, leitura_anexos, prestacao
from gestao.viagens.models import AnexoPrestacao, PrestacaoServidor

from .cenarios import cenario_completo
from .test_prestacao import _cliente

pytestmark = pytest.mark.django_db

COMPROVANTE = """BANCO EXEMPLO S.A.
Comprovante de transferência PIX
Data: 07/11/2026 14:02:11
Favorecido: ANA BEATRIZ CORREIA LIMA
Valor: R$ 1.205,78
Tarifa: R$ 0,00
Autenticação: A1B2.C3D4.E5F6.0718
"""


def _pdf(texto: str) -> bytes:
    from weasyprint import HTML
    html = "".join(f"<p>{linha}</p>" for linha in texto.splitlines())
    return HTML(string=f"<html><body>{html}</body></html>").write_pdf()


@pytest.fixture
def c(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return cenario_completo()


def _ps(c) -> PrestacaoServidor:
    return (PrestacaoServidor.objects.filter(prestacao__oficio_id=c.ids["oficio_emitido"])
            .select_related("servidor", "prestacao__oficio").order_by("servidor__nome").first())


# ------------------------------------------------------------- texto puro
def test_comprovante_autorizacao_data_valor_e_operacao():
    lido = leitura_anexos.ler_comprovante(COMPROVANTE)
    assert lido == {"valor": Decimal("1205.78"), "data": date(2026, 11, 7),
                    "autorizacao": "A1B2.C3D4.E5F6.0718", "operacao": "Pix"}


def test_comprovante_sem_rotulos_usa_o_maior_valor_e_o_hexadecimal_solto():
    texto = "SAQUE EM TERMINAL 05/11/2026 100,00 1.205,78 E0F1A2B3C4D5E6F7A8B9C0D1"
    lido = leitura_anexos.ler_comprovante(texto)
    assert lido["valor"] == Decimal("1205.78") and lido["operacao"] == "Saque"
    assert lido["autorizacao"] == "E0F1A2B3C4D5E6F7A8B9C0D1"


def test_conferir_com_a_diaria_do_oficio_e_do_rt():
    v = Decimal("1205.78")
    assert leitura_anexos.conferir(v, v, v) == [
        ("Bate com a diária do ofício (R$ 1.205,78)", "sucesso"),
        ("Bate com a diária do RT (R$ 1.205,78)", "sucesso")]
    assert leitura_anexos.conferir(Decimal("1000"), v, None) == [
        ("Difere da diária do ofício (R$ 1.205,78)", "perigo"),
        ("Sem diária do RT para conferir", "neutro")]
    # Dois comprovantes que somam a diária: cada um "difere", mas a soma bate.
    assert leitura_anexos.conferir(Decimal("605.78"), v, v, soma_comprovantes=v)[0][1] == "sucesso"
    assert leitura_anexos.conferir(None, v, v) == [("Valor não encontrado no comprovante", "aviso")]


def test_rt_e_diario_transcritos_pelos_rotulos_do_documento():
    rt = ("Nome Ana Beatriz\nCPF 123.456.700-88\nDiária: R$ 1.205,78\nTranslado: Não houve\n"
          "Descrição do evento\nApoio ao evento.\nConclusão\nFeito.\n")
    campos = leitura_anexos.ler_rt(rt)
    assert campos["Diária"] == "R$ 1.205,78" and campos["Nome"] == "Ana Beatriz"
    assert campos["Descrição do evento"] == "Apoio ao evento." and campos["Conclusão"] == "Feito."
    db = ("Viatura RENAULT MASTER Placa ABC1D23\nMotorista BRUNO MARTINS CPF 12345670169\n"
          "05/11/2026 09:00 10000 05/11/2026 16:30 10400 Curitiba/PR Arapongas/PR Sim\n")
    campos, trechos = leitura_anexos.ler_diario(db)
    assert campos["Viatura"] == "RENAULT MASTER" and campos["Placa"] == "ABC1D23"
    assert campos["Motorista"] == "BRUNO MARTINS" and len(trechos) == 1


def test_extrair_texto_so_de_pdf_com_texto():
    assert "Autenticação" in leitura_anexos.extrair_texto(_pdf(COMPROVANTE), "c.pdf")
    assert leitura_anexos.extrair_texto(b"%PDF-1.4 vazio", "c.pdf") == ""
    assert leitura_anexos.extrair_texto(b"\x89PNG....", "c.png") == ""


# ------------------------------------------------------------- a tela
def test_leitura_confere_o_comprovante_e_grava_o_lido(c):
    ps = _ps(c)
    op = c.usuarios["operador"]
    a = anexos.anexar(op, ps.prestacao_id, "comprovante", servidor_pk=ps.pk,
                      nome="pix.pdf", conteudo=_pdf(COMPROVANTE))
    anexos.anexar(op, ps.prestacao_id, "comprovante", servidor_pk=ps.pk,
                  nome="foto.png", conteudo=b"\x89PNG\r\n\x1a\n" + b"0" * 40)
    cliente = _cliente(c, "operador")
    r = cliente.get(reverse("viagens:leitura_prestacao", args=[ps.prestacao_id])
                    + f"?servidor={ps.pk}")
    html = r.content.decode()
    assert r.status_code == 200
    assert 'value="A1B2.C3D4.E5F6.0718"' in html and 'value="07/11/2026"' in html
    assert "Bate com a diária do ofício" in html
    assert "Imagem: não há texto para transcrever" in html
    assert "Documentos" in html and f"?servidor={ps.pk}" in html  # trilha e seletor
    # "Usar no comprovante" grava valor, data e operação lidos no anexo (acao_anexo).
    r = cliente.post(reverse("viagens:acao_anexo", args=[a.pk, "comprovante"]),
                     {"valor": "1205.78", "data_operacao": "07/11/2026", "operacao": "pix"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert (a.valor, a.data_operacao, a.operacao) == (Decimal("1205.78"), date(2026, 11, 7),
                                                      "pix")


def test_leitura_so_para_quem_ve_a_prestacao(c):
    ps = _ps(c)
    assert _cliente(c, "outra").get(
        reverse("viagens:leitura_prestacao", args=[ps.prestacao_id])).status_code == 404


# ------------------------------------------------------------- abas de pendência
def test_abas_sem_despacho_sem_comprovante_e_comprovante_diferente(c):
    a, b = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=c.ids["oficio_emitido"]).order_by("servidor__nome")
    todas = prestacao.ativos()
    assert set(prestacao.filtrar(todas, "sem_despacho")) == {a, b}
    assert set(prestacao.filtrar(todas, "sem_comprovante")) == {a, b}
    op = c.usuarios["operador"]
    anexos.anexar(op, a.prestacao_id, "despacho", nome="d.pdf", conteudo=b"%PDF-1.4 t")
    anexos.anexar(op, a.prestacao_id, "comprovante", servidor_pk=a.pk, nome="c.pdf",
                  conteudo=b"%PDF-1.4 t", valor=Decimal("10"))
    assert not prestacao.filtrar(todas, "sem_despacho").exists()
    assert set(prestacao.filtrar(todas, "sem_comprovante")) == {b}
    assert set(prestacao.filtrar(todas, "comprovante_diferente")) == {a}
    liberada = prestacao.diaria_liberada(a)
    AnexoPrestacao.objects.filter(servidor=a).update(valor=liberada)
    assert not prestacao.filtrar(todas, "comprovante_diferente").exists()
