"""RS-02 no resumo: projeção única, corrente/histórico, HTMX e escopo.

Casos para execução pelo coordenador em LAB; geração de arquivos não é necessária.
"""

from copy import deepcopy

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.models import MensagemOutbox
from gestao.viagens import documentos_versoes, services, views
from gestao.viagens.models import Documento, Historico, Oficio, ViaAssinada

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def emitido(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    Documento.objects.filter(oficio=oficio, tipo="oficio").update(
        situacao="pronto", sha256="a" * 64, arquivo="documentos/rs02-v1.pdf")
    return oficio


def _novo(oficio, *, versao=2, tipo="oficio", situacao="gerando", justificativa="",
          arquivo="documentos/rs02-v2.pdf"):
    dados = deepcopy(oficio.documentos.get(tipo="oficio", versao=1).dados)
    dados["motivo"] = "Texto da maior emissão, sem dados vivos."
    dados["justificativa"] = justificativa
    return Documento.objects.create(
        oficio=oficio, versao=versao, tipo=tipo, situacao=situacao, dados=dados,
        arquivo=arquivo, sha256="b" * 64 if situacao == "pronto" else "",
        emitido_por=oficio.criado_por)


def _via(documento, usuario, *, revogada=False):
    return ViaAssinada.objects.create(
        oficio=documento.oficio, documento=documento, tipo=documento.tipo,
        arquivo="assinados/rs02.pdf", sha256="c" * 64, tamanho=10, enviado_por=usuario,
        revogada_em=timezone.now() if revogada else None)


def _ler(client, cenario, oficio, *, perfil="operador"):
    client.force_login(cenario.usuarios[perfil])
    return client.get(reverse("viagens:resumo", args=[oficio.pk]), HTTP_HX_REQUEST="true")


def _rodape(resposta):
    texto = resposta.content.decode()
    return texto[texto.index('id="resumo-rodape"'):]


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_corrente_indisponivel_nao_promove_pdf_minuta_word_ou_assinatura(
        client, cenario, emitido, situacao):
    anterior = emitido.documentos.get(tipo="oficio", versao=1)
    _via(anterior, cenario.usuarios["operador"])
    atual = _novo(emitido, situacao=situacao)
    resposta = _ler(client, cenario, emitido)
    assert resposta.status_code == 200
    contexto = resposta.context
    assert contexto["pdf_oficio"] is None and contexto["pdf_oficio_url"] == ""
    assert contexto["docx_oficio"] is None and contexto["vias"] == []
    assert contexto["menu"].pdf is None and not contexto["menu"].minuta
    assert [linha["documento"].pk for linha in contexto["documentos_correntes"]] == [atual.pk]
    assert [linha["documento"].pk for linha in contexto["documentos_historicos"]] == [anterior.pk]
    assert contexto["copia"].disponivel and contexto["copia"].versao == 2
    assert contexto["gerando"] is (situacao == "gerando")
    rodape = _rodape(resposta)
    assert reverse("viagens:previa", args=[emitido.pk]) not in rodape
    assert reverse("viagens:baixar_docx", args=[emitido.pk, "oficio"]) not in rodape
    assert reverse("viagens:baixar_documento", args=[anterior.pk]) not in rodape
    assert "Histórico de documentos" in resposta.content.decode()


def test_historico_gerando_nao_mantem_polling_da_emissao_pronta(client, cenario, emitido):
    Documento.objects.filter(oficio=emitido, versao=1).update(situacao="gerando")
    atual = _novo(emitido, situacao="pronto")
    resposta = _ler(client, cenario, emitido)
    assert resposta.context["pdf_oficio"].pk == atual.pk
    assert not resposta.context["gerando"]
    assert "data-resumo-poll" not in resposta.content.decode()


def test_retry_so_da_corrente_falha_nao_da_historica(client, cenario, emitido):
    antiga = emitido.documentos.get(tipo="oficio", versao=1)
    Documento.objects.filter(pk=antiga.pk).update(situacao="falhou")
    atual = _novo(emitido, situacao="falhou")
    html = _ler(client, cenario, emitido).content.decode()
    assert reverse("viagens:regenerar_documento", args=[atual.pk]) in html
    assert reverse("viagens:regenerar_documento", args=[antiga.pk]) not in html


@pytest.mark.parametrize("situacao", ["pronto", "falhou"])
def test_contexto_herdado_de_historico_nao_reclassifica_corrente(
        client, cenario, emitido, situacao):
    atual = _novo(emitido, situacao=situacao)
    resposta = _ler(client, cenario, emitido)
    contexto = views._contexto_resumo(resposta.wsgi_request, emitido)
    contexto["historico"] = list(Historico.objects.filter(oficio=emitido))
    assert contexto["historico"]  # histórico de negócio legítimo herdado da folha
    html = render_to_string("viagens/oficios/_resumo.html", contexto,
                            request=resposta.wsgi_request)
    assert "Ofício v2 (histórico)" not in html
    assert "Ofício v1 (histórico)" in html
    retry = reverse("viagens:regenerar_documento", args=[atual.pk])
    assert (retry in html) is (situacao == "falhou")


def test_pronto_sem_caminho_nao_cria_link_pdf_mas_preserva_word(client, cenario, emitido):
    atual = _novo(emitido, situacao="pronto", arquivo="")
    resposta = _ler(client, cenario, emitido)
    assert resposta.context["pdf_oficio"] is None
    assert resposta.context["pdf_oficio_url"] == ""
    assert resposta.context["docx_oficio"].pk == atual.pk
    assert "PDF indisponível" in resposta.content.decode()
    assert reverse("viagens:baixar_documento", args=[atual.pk]) not in resposta.content.decode()
    assert "Baixar em Word" in _rodape(resposta)


def test_via_exata_e_original_sem_caminho_tem_leitura_assinada(client, cenario, emitido):
    atual = _novo(emitido, situacao="pronto", arquivo="")
    via = _via(atual, cenario.usuarios["operador"])
    resposta = _ler(client, cenario, emitido)
    assert resposta.context["pdf_oficio"] is None
    assert resposta.context["pdf_oficio_url"] == reverse(
        "viagens:abrir_via_assinada", args=[via.pk])
    assert resposta.context["vias"][0]["s"]["via"].pk == via.pk
    assert "Ver o PDF" in _rodape(resposta)
    assert reverse("viagens:baixar_documento", args=[atual.pk]) not in resposta.content.decode()


@pytest.mark.parametrize("justificativa", ["", None, {"texto": "shape inválido"}])
def test_justificativa_antiga_aparece_apenas_no_historico(
        client, cenario, emitido, justificativa):
    atual = _novo(emitido, situacao="pronto", justificativa=justificativa)
    antiga = _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _via(antiga, cenario.usuarios["operador"])
    resposta = _ler(client, cenario, emitido)
    assert [linha["documento"].pk for linha in resposta.context["documentos_correntes"]] == [
        atual.pk]
    assert any(linha["documento"].pk == antiga.pk
               for linha in resposta.context["documentos_historicos"])
    assert resposta.context["menu"].justificativa is None
    assert len(resposta.context["vias"]) == 1
    assert "Via assinada histórica" in resposta.content.decode()


def test_reaberto_mostra_minuta_e_vias_revogadas_no_historico(client, cenario, emitido):
    anterior = emitido.documentos.get(tipo="oficio", versao=1)
    via = _via(anterior, cenario.usuarios["operador"])
    services.reabrir(emitido, cenario.usuarios["gestor"], "Corrigir o destino.")
    emitido.refresh_from_db()
    resposta = _ler(client, cenario, emitido)
    assert resposta.context["documentos_correntes"] == []
    assert not resposta.context["gerando"] and resposta.context["menu"].minuta
    assert "Ver minuta" in _rodape(resposta) and "Ver o PDF" not in _rodape(resposta)
    assert "Via assinada histórica · revogada" in resposta.content.decode()
    assert reverse("viagens:abrir_via_assinada", args=[via.pk]) in resposta.content.decode()
    assert resposta.context["copia"].fonte == "rascunho"


def test_cancelado_conserva_links_exatos_sem_corrente(client, cenario, emitido):
    documento = emitido.documentos.get(tipo="oficio", versao=1)
    via = _via(documento, cenario.usuarios["operador"], revogada=True)
    emitido.situacao = "cancelado"
    emitido.motivo_cancelamento = "Evento cancelado."
    emitido.save(update_fields=["situacao", "motivo_cancelamento"])
    resposta = _ler(client, cenario, emitido, perfil="consulta")
    assert resposta.context["documentos_correntes"] == []
    assert not resposta.context["gerando"] and not resposta.context["menu"].minuta
    assert reverse("viagens:baixar_documento", args=[documento.pk]) in resposta.content.decode()
    assert reverse("viagens:abrir_via_assinada", args=[via.pk]) in resposta.content.decode()
    assert "Ver minuta" not in _rodape(resposta)
    assert resposta.context["copia"].disponivel and "cancelado" in resposta.context["copia"].aviso


def test_projecao_materializada_uma_vez_com_todas_as_vias_sem_sql(
        client, cenario, emitido, monkeypatch, django_assert_num_queries):
    anterior = emitido.documentos.get(tipo="oficio", versao=1)
    revogada = _via(anterior, cenario.usuarios["operador"], revogada=True)
    atual = _novo(emitido, situacao="pronto")
    ativa = _via(atual, cenario.usuarios["operador"])
    projetar = documentos_versoes.projetar_documentos
    chamadas = []

    def observar(oficio, *, documentos, vias):
        assert isinstance(documentos, list) and isinstance(vias, list)
        chamadas.append(({d.pk for d in documentos}, {v.pk for v in vias}))
        with django_assert_num_queries(0):
            return projetar(oficio, documentos=documentos, vias=vias)

    monkeypatch.setattr(documentos_versoes, "projetar_documentos", observar)
    resposta = _ler(client, cenario, emitido)
    assert resposta.status_code == 200
    assert chamadas == [({anterior.pk, atual.pk}, {revogada.pk, ativa.pk})]


def test_polling_atualiza_documentos_rodape_e_copia_em_ids_estaveis(client, cenario, emitido):
    atual = _novo(emitido, situacao="gerando")
    primeira = _ler(client, cenario, emitido)
    html = primeira.content.decode()
    assert 'data-resumo-poll hx-get=' in html
    assert 'hx-select-oob="#resumo-rodape,#resumo-copia-area"' in html
    assert 'id="resumo-rodape" tabindex="-1" role="group"' in html
    assert "Ver o PDF" not in _rodape(primeira)
    Documento.objects.filter(pk=atual.pk).update(situacao="pronto", sha256="b" * 64)
    pronta = _ler(client, cenario, emitido)
    assert "data-resumo-poll" not in pronta.content.decode()
    assert "Ver o PDF" in _rodape(pronta) and "Baixar em Word" in _rodape(pronta)
    assert pronta.context["copia"].versao == 2
    assert pronta.content.decode().count('id="resumo-copia-area"') == 1
    assert pronta.content.decode().count('id="resumo-rodape"') == 1


@pytest.mark.parametrize("perfil,status", [("consulta", 200), ("operador", 200),
                                         ("gestor", 200), ("outra", 404)])
def test_resumo_preserva_autorizacao(client, cenario, emitido, perfil, status):
    assert _ler(client, cenario, emitido, perfil=perfil).status_code == status


def test_leitura_do_resumo_nao_escreve_negocio(client, cenario, emitido):
    _novo(emitido, situacao="falhou")
    antes = Oficio.objects.filter(pk=emitido.pk).values().get()
    documentos = list(emitido.documentos.values())
    historico = Historico.objects.filter(oficio=emitido).count()
    mensagens = MensagemOutbox.objects.count()
    assert _ler(client, cenario, emitido).status_code == 200
    assert Oficio.objects.filter(pk=emitido.pk).values().get() == antes
    assert list(emitido.documentos.values()) == documentos
    assert Historico.objects.filter(oficio=emitido).count() == historico
    assert MensagemOutbox.objects.count() == mensagens


@pytest.mark.parametrize("chave,limite", [("oficio_rascunho", 20), ("oficio_emitido", 15)])
def test_budget_resumo_preservado(
        client, cenario, chave, limite, django_assert_max_num_queries):
    client.force_login(cenario.usuarios["operador"])
    with django_assert_max_num_queries(limite):
        resposta = client.get(reverse("viagens:resumo", args=[cenario.ids[chave]]))
        assert resposta.status_code == 200
