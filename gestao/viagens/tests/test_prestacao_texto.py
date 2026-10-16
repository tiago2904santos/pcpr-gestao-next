"""Os documentos da prestação no editor (ADR 0018 / ADR 0042): o diário e o RT de cada
servidor saem na folha e no PDF com o texto editado por região; versões, voltar ao modelo,
conflito e permissão; os documentos com a composição do sistema modelo."""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from gestao.viagens import diario, leitura_anexos, prestacao_texto, relatorio
from gestao.viagens.models import EdicaoPrestacao, PrestacaoContas, PrestacaoServidor

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _prestacao(c) -> tuple[PrestacaoContas, PrestacaoServidor]:
    p = PrestacaoContas.objects.select_related("oficio").get(oficio_id=c.ids["oficio_emitido"])
    ps = PrestacaoServidor.objects.filter(prestacao=p).select_related("servidor") \
        .order_by("servidor__nome").first()
    return p, ps


def _cliente(c, login="operador") -> Client:
    cliente = Client()
    cliente.force_login(c.usuarios[login])
    return cliente


def test_documentos_da_prestacao_como_no_modelo(c):
    p, ps = _prestacao(c)
    d = diario.obter(p)
    diario.salvar_linhas(c.usuarios["operador"], d.pk, {
        linha.pk: {"km_inicial": 10000 + i * 400, "km_final": 10380 + i * 400}
        for i, linha in enumerate(diario.linhas(d))})
    texto = leitura_anexos.extrair_texto(prestacao_texto.pdf_do_documento(
        prestacao_texto.dados_do_documento(p, "diario")), "d.pdf")
    # O diário do modelo: rótulos no texto das células, abastecimento marcado, motorista na tabela.
    assert "Referente ao Ofício: 01/2026" in texto and "Placa oficial:" in texto
    assert "( X ) Sim" in texto and "Assinatura:" in texto and "KM (inicial)" in texto
    rt = relatorio.obter(p)
    relatorio.salvar(c.usuarios["operador"], rt.pk, {"motivo": "Apoio ao evento (teste)."})
    texto = leitura_anexos.extrair_texto(prestacao_texto.pdf_do_documento(
        prestacao_texto.dados_do_documento(p, prestacao_texto.chave_rt(ps.pk))), "rt.pdf")
    assert "RELATÓRIO TÉCNICO DE VIAGEM" in texto and "VALORES UTILIZADOS NA VIAGEM" in texto
    assert "Declaramos que o trabalho previsto" in texto
    assert f"CPF {ps.servidor.cpf_formatado}" in texto
    assert "Apoio ao evento (teste)." in texto
    # A leitura dos anexos entende o RT que o próprio sistema gera.
    campos = leitura_anexos.ler_rt(texto)
    assert campos["Nome"] == ps.servidor.nome and campos["Descrição do evento"].startswith("Apoio")


def test_texto_editado_vale_para_a_folha_o_pdf_e_as_versoes(c):
    p, ps = _prestacao(c)
    chave = prestacao_texto.chave_rt(ps.pk)
    cliente = _cliente(c)
    estado = cliente.get(reverse("viagens:editor_prestacao_estado", args=[p.pk, chave])).json()
    assert estado["pode_editar"] and estado["edicao"] is None
    assert [r["chave"] for r in estado["regioes"]] == ["corpo", "assinatura"]
    r = cliente.post(reverse("viagens:editor_prestacao_salvar", args=[p.pk, chave]),
                     {"regioes": {"assinatura": '<div class="assinatura"><p>CPF editado</p></div>'},
                      "versao_base": 0}, content_type="application/json")
    assert r.status_code == 200 and r.json()["resultado"]["versao"] == 1
    assert EdicaoPrestacao.objects.filter(prestacao=p, chave=chave).count() == 1
    folha = cliente.get(reverse("viagens:folha_relatorio", args=[p.pk, ps.pk])).content.decode()
    assert "CPF editado" in folha
    pdf = cliente.get(reverse("viagens:documento_relatorio", args=[p.pk, ps.pk, "pdf"]))
    assert "CPF editado" in leitura_anexos.extrair_texto(pdf.content, "rt.pdf")
    # ?versao=0 é o modelo; a versão que não existe é 404.
    modelo = cliente.get(reverse("viagens:folha_relatorio", args=[p.pk, ps.pk]) + "?versao=0")
    assert "CPF editado" not in modelo.content.decode()
    assert cliente.get(reverse("viagens:folha_relatorio", args=[p.pk, ps.pk])
                       + "?versao=9").status_code == 404
    # Conflito: salvar sobre uma versão que já mudou.
    r = cliente.post(reverse("viagens:editor_prestacao_salvar", args=[p.pk, chave]),
                     {"regioes": {"assinatura": "<p>outra</p>"}, "versao_base": 0},
                     content_type="application/json")
    assert r.status_code == 409
    # Voltar ao modelo cria uma versão nova, sem regiões.
    r = cliente.post(reverse("viagens:editor_prestacao_modelo", args=[p.pk, chave]))
    assert r.status_code == 200 and r.json()["edicao"]["do_modelo"]
    assert "CPF editado" not in cliente.get(
        reverse("viagens:folha_relatorio", args=[p.pk, ps.pk])).content.decode()
    # O diário tem a sua própria chave e as suas versões.
    r = cliente.post(reverse("viagens:editor_prestacao_salvar", args=[p.pk, "diario"]),
                     {"regioes": {"corpo": "<table><tr><td>Diário editado</td></tr></table>"}},
                     content_type="application/json")
    assert r.status_code == 200
    assert "Diário editado" in cliente.get(
        reverse("viagens:folha_diario", args=[p.pk])).content.decode()


def test_chave_invalida_consulta_e_prestacao_finalizada(c):
    p, _ps = _prestacao(c)
    cliente = _cliente(c)
    assert cliente.get(reverse("viagens:editor_prestacao_estado",
                               args=[p.pk, "rt-999"])).status_code == 404
    assert cliente.get(reverse("viagens:editor_prestacao_estado",
                               args=[p.pk, "outra"])).status_code == 404
    consulta = _cliente(c, "consulta")
    estado = consulta.get(reverse("viagens:editor_prestacao_estado", args=[p.pk, "diario"]))
    assert estado.status_code == 200 and not estado.json()["pode_editar"]
    r = consulta.post(reverse("viagens:editor_prestacao_salvar", args=[p.pk, "diario"]),
                      {"regioes": {"corpo": "<p>x</p>"}}, content_type="application/json")
    assert r.status_code == 403
    assert _cliente(c, "outra").get(reverse("viagens:editor_prestacao_estado",
                                             args=[p.pk, "diario"])).status_code == 404
