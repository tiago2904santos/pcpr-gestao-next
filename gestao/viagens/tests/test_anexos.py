"""Anexos da prestação (módulo 9d): validação pelo conteúdo, despacho e comprovante somam,
assinados substituem, remover/voltar em 30 dias, comprovantes conferidos com a diária,
trava (servidor × equipe), pendências da finalização, permissões e a tela."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.viagens import anexos, prestacao
from gestao.viagens.models import AnexoPrestacao, PrestacaoContas, PrestacaoServidor

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4 teste"
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def c():
    return cenario_completo()


def _p(c) -> PrestacaoContas:
    return PrestacaoContas.objects.select_related("oficio").get(
        oficio_id=c.ids["oficio_emitido"])


def _servidores(p) -> list[PrestacaoServidor]:
    return list(prestacao.ativos().filter(prestacao=p).select_related("servidor")
                .order_by("servidor__nome"))


def _cliente(c, login: str) -> Client:
    cliente = Client()
    cliente.force_login(c.usuarios[login])
    return cliente


def test_validacao_pelo_conteudo():
    anexos.validar("a.pdf", 10, PDF)
    anexos.validar("foto.PNG", 10, PNG)
    with pytest.raises(anexos.AnexoInvalido, match="PDF ou uma imagem"):
        anexos.validar("a.docx", 10, PDF)
    with pytest.raises(anexos.AnexoInvalido, match="10 MB"):
        anexos.validar("a.pdf", anexos.TAMANHO_MAXIMO + 1, PDF)
    with pytest.raises(anexos.AnexoInvalido, match="não confere"):
        anexos.validar("a.pdf", 10, PNG)


def test_somam_e_assinados_substituem_e_voltam(c):
    p = _p(c)
    a, _ = _servidores(p)
    op = c.usuarios["operador"]
    anexos.anexar(op, p.pk, "despacho", nome="d1.pdf", conteudo=PDF)
    anexos.anexar(op, p.pk, "despacho", nome="d2.pdf", conteudo=PDF)
    assert anexos.ativos(AnexoPrestacao.objects.filter(tipo="despacho")).count() == 2
    rt1 = anexos.anexar(op, p.pk, "rt_assinado", servidor_pk=a.pk, nome="rt1.pdf", conteudo=PDF)
    rt2 = anexos.anexar(op, p.pk, "rt_assinado", servidor_pk=a.pk, nome="rt2.pdf", conteudo=PDF)
    rt1.refresh_from_db()
    assert rt1.removido_motivo == "substituido" and not rt2.removido
    # Voltar o anterior tira o atual de uso.
    anexos.restaurar(op, rt1.pk)
    rt2.refresh_from_db()
    assert rt2.removido and list(anexos.versoes_anteriores(p)) == [rt2]
    with pytest.raises(anexos.AnexoInvalido, match="Escolha o servidor"):
        anexos.anexar(op, p.pk, "comprovante", nome="c.pdf", conteudo=PDF)
    # Mais de 30 dias: não volta.
    AnexoPrestacao.objects.filter(pk=rt2.pk).update(
        removido_em=timezone.now() - timedelta(days=31))
    with pytest.raises(anexos.AnexoInvalido, match="30 dias"):
        anexos.restaurar(op, rt2.pk)


def test_comprovantes_conferidos_com_a_diaria(c):
    p = _p(c)
    a, _ = _servidores(p)
    a.prestacao = p
    op = c.usuarios["operador"]
    liberada = prestacao.diaria_liberada(a)
    meio = (liberada / 2).quantize(Decimal("0.01"))
    c1 = anexos.anexar(op, p.pk, "comprovante", servidor_pk=a.pk, nome="c1.pdf", conteudo=PDF,
                       valor=meio, data_operacao=date(2030, 1, 7), operacao="saque")
    pend = prestacao.pendencias(a)
    assert any(t.startswith("Os comprovantes somam") for t in pend)
    anexos.anexar(op, p.pk, "comprovante", servidor_pk=a.pk, nome="c2.pdf", conteudo=PDF,
                  valor=liberada - meio)
    assert not any(t.startswith("Os comprovantes somam") for t in prestacao.pendencias(a))
    # Um comprovante sem valor: não dá para saber — sem aviso.
    anexos.editar_comprovante(op, c1.pk, valor=None, data_operacao=None, operacao="")
    assert not any(t.startswith("Os comprovantes somam") for t in prestacao.pendencias(a))
    with pytest.raises(anexos.AnexoInvalido, match="maior que zero"):
        anexos.editar_comprovante(op, c1.pk, valor=Decimal("0"), data_operacao=None,
                                  operacao="")


def test_pendencias_na_ordem_da_referencia(c):
    p = _p(c)
    a, _ = _servidores(p)
    assert prestacao.pendencias(a)[:3] == [
        "Informe o número da solicitação deste servidor.",
        "Anexe o despacho assinado do ofício.",
        "Anexe o comprovante de saque/transferência deste servidor."]
    assert not any("prazo" in t for t in prestacao.pendencias(a))  # a referência não cobra
    op = c.usuarios["operador"]
    anexos.anexar(op, p.pk, "db_assinado", nome="db.pdf", conteudo=PDF)
    anexos.anexar(op, p.pk, "rt_assinado", servidor_pk=a.pk, nome="rt.pdf", conteudo=PDF)
    from gestao.viagens import diario, relatorio
    texto = prestacao.pendencias(a)
    assert diario.PENDENCIA not in texto and relatorio.PENDENCIA not in texto


def test_trava_servidor_e_equipe(c):
    p = _p(c)
    a, b = _servidores(p)
    op = c.usuarios["operador"]
    prestacao.finalizar(op, a.pk, "Teste.")
    with pytest.raises(anexos.AnexoInvalido, match="reabra"):
        anexos.anexar(op, p.pk, "comprovante", servidor_pk=a.pk, nome="c.pdf", conteudo=PDF)
    anexos.anexar(op, p.pk, "despacho", nome="d.pdf", conteudo=PDF)  # equipe ainda aberta
    prestacao.finalizar(op, b.pk, "Teste.")
    with pytest.raises(anexos.AnexoInvalido, match="reabra"):
        anexos.anexar(op, p.pk, "despacho", nome="d2.pdf", conteudo=PDF)


def test_permissoes(c):
    p = _p(c)
    a, _ = _servidores(p)
    anexo = anexos.anexar(c.usuarios["operador"], p.pk, "comprovante", servidor_pk=a.pk,
                          nome="c.pdf", conteudo=PDF)
    outra, consulta = _cliente(c, "outra"), _cliente(c, "consulta")
    assert outra.get(reverse("viagens:documentos_prestacao", args=[p.pk])).status_code == 404
    assert outra.get(reverse("viagens:abrir_anexo", args=[anexo.pk])).status_code == 404
    assert outra.post(reverse("viagens:acao_anexo", args=[anexo.pk, "remover"])).status_code == 404
    r = consulta.get(reverse("viagens:documentos_prestacao", args=[p.pk]))
    assert r.status_code == 200 and 'type="file"' not in r.content.decode()
    assert consulta.get(reverse("viagens:abrir_anexo", args=[anexo.pk])).status_code == 200
    consulta.post(reverse("viagens:acao_anexo", args=[anexo.pk, "remover"]))
    anexo.refresh_from_db()
    assert not anexo.removido


def test_tela_anexar_abrir_remover(c):
    p = _p(c)
    a, _ = _servidores(p)
    op = _cliente(c, "operador")
    r = op.get(reverse("viagens:documentos_prestacao", args=[p.pk]))
    assert r.status_code == 200 and "Despacho assinado" in r.content.decode()
    r = op.post(reverse("viagens:anexar_prestacao", args=[p.pk]), {
        "tipo": "comprovante", "servidor": a.pk, "valor": "R$ 100,00",
        "data_operacao": "07/01/2030", "operacao": "pix",
        "arquivo": SimpleUploadedFile("comprovante.png", PNG + b"x" * 20, "image/png")})
    assert r["Location"].endswith(f"#ps-{a.pk}")
    anexo = AnexoPrestacao.objects.get(tipo="comprovante")
    assert (anexo.valor, anexo.data_operacao, anexo.operacao) == (
        Decimal("100.00"), date(2030, 1, 7), "pix")
    r = op.get(reverse("viagens:abrir_anexo", args=[anexo.pk]))
    assert r["Content-Type"] == "image/png" and r["X-Content-Type-Options"] == "nosniff"
    r = op.post(reverse("viagens:anexar_prestacao", args=[p.pk]), {
        "tipo": "despacho", "arquivo": SimpleUploadedFile("x.pdf", PNG, "application/pdf")},
        follow=True)
    assert "não confere" in r.content.decode()
    op.post(reverse("viagens:acao_anexo", args=[anexo.pk, "remover"]))
    anexo.refresh_from_db()
    assert anexo.removido_motivo == "excluido"
    assert "Trazer de volta" in op.get(
        reverse("viagens:documentos_prestacao", args=[p.pk])).content.decode()
    assert reverse("viagens:documentos_prestacao", args=[p.pk]) in op.get(
        reverse("viagens:prestacoes")).content.decode()
    assert op.post(reverse("viagens:acao_anexo", args=[anexo.pk, "xyz"])).status_code == 404
