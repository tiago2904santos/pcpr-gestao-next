"""HTML real do menu e arquivos por identidade exata: defesa de versão/dono/tipo."""
from __future__ import annotations

from copy import deepcopy

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from gestao.viagens import services
from gestao.viagens.models import Documento, ViaAssinada
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def original(cenario, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    doc = Documento.objects.get(oficio_id=cenario.ids["oficio_emitido"], tipo="oficio")
    doc.situacao = "pronto"
    doc.sha256 = "a" * 64
    doc.arquivo.save("original.pdf", ContentFile(b"%PDF-original-por-identidade"))
    doc.save()
    return doc


@pytest.mark.parametrize("estado", ["gerando", "falhou", "cancelado"])
def test_menu_html_nao_oferece_minuta_nem_v1_com_emissao_indisponivel(
        client, cenario, original, estado):
    oficio = original.oficio
    Documento.objects.create(oficio=oficio, tipo="oficio", versao=2,
                             situacao="pronto" if estado == "cancelado" else estado,
                             sha256="b" * 64 if estado == "cancelado" else "",
                             dados=deepcopy(original.dados), emitido_por=oficio.criado_por)
    if estado == "cancelado":
        services.cancelar(oficio, cenario.usuarios["gestor"], "Evento cancelado no cenário LAB.")
    client.force_login(cenario.usuarios["operador"])
    resposta = client.get(reverse("viagens:acoes_oficio", args=[oficio.pk]))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert reverse("viagens:previa", args=[oficio.pk]) not in html
    assert reverse("viagens:baixar_documento", args=[original.pk]) not in html
    assert "Ver minuta" not in html


def test_menu_html_rascunho_preserva_minuta(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    pk = cenario.ids["oficio_rascunho"]
    resposta = client.get(reverse("viagens:acoes_oficio", args=[pk]))
    assert resposta.status_code == 200
    assert reverse("viagens:previa", args=[pk]) in resposta.content.decode()


@pytest.mark.parametrize("defeito", ["vazio", "branco", "dono", "tipo"])
def test_pdf_exato_nao_entrega_via_invalida(client, cenario, original, defeito):
    oficio = original.oficio
    via = ViaAssinada.objects.create(
        oficio_id=cenario.ids["oficio_outra_unidade"] if defeito == "dono" else oficio.pk,
        documento=original, tipo="justificativa" if defeito == "tipo" else "oficio",
        enviado_por=cenario.usuarios["operador"], sha256="b" * 64, tamanho=10)
    if defeito in {"dono", "tipo"}:
        via.arquivo.save("outra-via.pdf", ContentFile(b"%PDF-via-que-nao-pertence"))
    elif defeito == "branco":
        via.arquivo = "   "
        via.save(update_fields=["arquivo"])
    client.force_login(cenario.usuarios["consulta"])
    resposta = client.get(reverse("viagens:baixar_documento", args=[original.pk]))
    assert resposta.status_code == 200
    assert b"".join(resposta.streaming_content) == b"%PDF-original-por-identidade"
    assert resposta["X-Content-SHA256"] == original.sha256


def test_via_exata_valida_e_opcao_original_preservadas(client, cenario, original):
    via = ViaAssinada.objects.create(
        oficio=original.oficio, documento=original, tipo="oficio",
        enviado_por=cenario.usuarios["operador"], sha256="b" * 64, tamanho=10)
    via.arquivo.save("via-valida.pdf", ContentFile(b"%PDF-via-valida"))
    client.force_login(cenario.usuarios["consulta"])
    url = reverse("viagens:baixar_documento", args=[original.pk])
    resposta = client.get(url)
    assert resposta.status_code == 200
    assert b"".join(resposta.streaming_content) == b"%PDF-via-valida"
    assert resposta["X-Content-SHA256"] == via.sha256
    original_lido = client.get(url, {"versao": "original"})
    assert b"".join(original_lido.streaming_content) == b"%PDF-original-por-identidade"


@pytest.mark.parametrize("arquivo", ["", "   ", "documentos/arquivo-ausente.pdf"])
def test_arquivo_original_indisponivel_retorna_404(client, cenario, original, arquivo):
    original.arquivo = arquivo
    original.save(update_fields=["arquivo"])
    client.force_login(cenario.usuarios["consulta"])
    resposta = client.get(reverse("viagens:baixar_documento", args=[original.pk]),
                          {"versao": "original"})
    assert resposta.status_code == 404


@pytest.mark.parametrize("formato", ["pdf", "docx"])
def test_pacote_inclui_justificativa_esperada_ausente_sem_minuta(original, formato, client):
    from gestao.viagens import pacotes

    dados = deepcopy(original.dados)
    dados["justificativa"] = "Justificativa da emissão que precisa acompanhar o ofício."
    original.dados = dados
    original.save(update_fields=["dados"])
    itens = pacotes.itens_da_justificativa(original.oficio)
    assert [item.valor for item in itens] == ["justificativa", "oficio"]
    assert itens[0].estado == "PDF indisponível" and itens[0].via is None
    with pytest.raises(pacotes.PacoteInvalido, match=r"justificativa.*indisponível"):
        pacotes.montar(itens, ["justificativa"], formato=formato, versao="original",
                      saida="separados", nome_base="oficio")
    client.force_login(original.oficio.criado_por)
    url = reverse("viagens:baixar_oficio", args=[original.oficio_id])
    pedido = {"itens": ["justificativa"], "formato": formato}
    resposta = client.post(url, pedido, headers={"X-Requested-With": "fetch"})
    assert resposta.status_code == 422
    assert "justificativa" in resposta.json()["erro"]
    assert "indisponível" in resposta.json()["erro"]
    assert resposta["Cache-Control"] == "no-store"
    assert client.post(url, pedido).status_code == 302
