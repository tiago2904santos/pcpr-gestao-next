"""RS-02 integrado: identidade máxima, snapshot, autorização e SQL constante.

Execução em LAB pelo coordenador; não depende do worker nem gera PDF real.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from gestao.plataforma.models import MensagemOutbox
from gestao.viagens import assinados, pacotes, policies, queries, services, views
from gestao.viagens.documentos_versoes import projetar_documentos
from gestao.viagens.models import Documento, Historico, Oficio, ViaAssinada

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def emitido(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    documento = oficio.documentos.get(tipo="oficio", versao=1)
    documento.situacao = "pronto"
    documento.arquivo = "documentos/rs02-v1.pdf"
    documento.sha256 = "1" * 64
    documento.save(update_fields=["situacao", "arquivo", "sha256"])
    return oficio


def _novo(oficio, *, tipo="oficio", versao=2, situacao="gerando", justificativa="",
          arquivo="documentos/rs02-v2.pdf"):
    dados = deepcopy(oficio.documentos.get(tipo="oficio", versao=1).dados)
    dados["justificativa"] = justificativa
    return Documento.objects.create(
        oficio=oficio, tipo=tipo, versao=versao, situacao=situacao, dados=dados,
        arquivo=arquivo, sha256="2" * 64 if situacao == "pronto" else "",
        emitido_por=oficio.criado_por)


def _via(documento, usuario, *, revogada=False, arquivo="assinados/rs02.pdf"):
    return ViaAssinada.objects.create(
        oficio=documento.oficio, documento=documento, tipo=documento.tipo,
        arquivo=arquivo, sha256="a" * 64, tamanho=10, enviado_por=usuario,
        revogada_em=timezone.now() if revogada else None)


def _anotado(oficio):
    return queries.com_dados_de_lista(Oficio.objects.filter(pk=oficio.pk)).get()


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_corrente_nao_promove_v1_no_menu_anexacao_docx_ou_pacote(
        cenario, emitido, situacao, client, monkeypatch, django_assert_num_queries):
    ultimo = _novo(emitido, situacao=situacao)
    anotado = _anotado(emitido)
    with django_assert_num_queries(0):
        menu = policies.menu_do_oficio(cenario.usuarios["operador"], anotado)
    assert menu.pdf is None and not menu.minuta and menu.anexar == "inativo"
    assert ("falhou" if situacao == "falhou" else "sendo gerado") in menu.anexar_motivo
    selecao = queries.selecao_documental_da_lista(anotado, "oficio")
    assert selecao is not None and selecao.ultima_emissao is not None
    assert selecao.ultima_emissao.id == ultimo.pk
    assert assinados.documento_emitido(emitido, "oficio") is None

    def impedir_dados_vivos(*args, **kwargs):
        pytest.fail("Emitido não pode reconstituir dados vivos para contornar a geração.")

    monkeypatch.setattr("gestao.viagens.documentos.dados.dados_do_oficio", impedir_dados_vivos)
    monkeypatch.setattr(views, "dados_do_oficio", impedir_dados_vivos)
    client.force_login(cenario.usuarios["operador"])
    resposta = client.get(reverse("viagens:baixar_docx", args=[emitido.pk, "oficio"]))
    assert resposta.status_code == 422 and b"DOCX" in resposta.content
    itens = pacotes.itens_da_justificativa(emitido)
    assert itens[0].estado != "Minuta" and itens[0].via is None
    for formato in ("pdf", "docx"):
        with pytest.raises(pacotes.PacoteInvalido, match=r"falhou|sendo gerado"):
            pacotes.montar(itens, ["oficio"], formato=formato, versao="original",
                          saida="separados", nome_base="oficio")


@pytest.mark.parametrize("justificativa", ["", "  ", None, {"texto": "inválido"}])
def test_snapshot_nao_promove_justificativa_antiga(
        cenario, emitido, justificativa, django_assert_num_queries):
    emitido.justificativa = "Texto vivo não decide a emissão."
    emitido.save(update_fields=["justificativa"])
    _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _novo(emitido, situacao="pronto", justificativa=justificativa)
    anotado = _anotado(emitido)
    with django_assert_num_queries(0):
        menu = policies.menu_do_oficio(cenario.usuarios["operador"], anotado)
        assert queries.pdf_corrente_da_lista(anotado, "justificativa") is None
    assert menu.justificativa is None
    assert assinados.documento_emitido(emitido, "justificativa") is None
    assert [item.valor for item in pacotes.itens_da_justificativa(emitido)] == ["oficio"]


def test_justificativa_snapshot_presente_independe_do_texto_vivo(emitido):
    emitido.justificativa = ""
    emitido.save(update_fields=["justificativa"])
    _novo(emitido, situacao="pronto", justificativa="Urgência congelada.")
    justificativa = _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    selecionada = assinados.documento_emitido(emitido, "justificativa")
    assert selecionada is not None and selecionada.pk == justificativa.pk
    assert [item.valor for item in pacotes.itens_da_justificativa(emitido)] == [
        "justificativa", "oficio"]


@pytest.mark.parametrize("situacao", ["gerando", "falhou"])
def test_justificativa_maior_indisponivel_nao_promove_v1(emitido, situacao):
    _novo(emitido, situacao="pronto", justificativa="Urgência congelada.")
    _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _novo(emitido, tipo="justificativa", versao=2, situacao=situacao)
    assert queries.pdf_corrente_da_lista(_anotado(emitido), "justificativa") is None
    item = pacotes.itens_da_justificativa(emitido)[0]
    assert item.valor == "justificativa"
    with pytest.raises(pacotes.PacoteInvalido):
        item.docx()


def test_assinatura_de_v1_nao_assina_v2(cenario, emitido, django_assert_num_queries):
    anterior = emitido.documentos.get(tipo="oficio", versao=1)
    _via(anterior, cenario.usuarios["operador"])
    ultimo = _novo(emitido, situacao="pronto")
    anotado = _anotado(emitido)
    assert not anotado.via_oficio
    assert assinados.vigente(assinados.Alvo("oficio", emitido)) is None
    with django_assert_num_queries(0):
        menu = policies.menu_do_oficio(cenario.usuarios["operador"], anotado)
    assert menu.pdf == (ultimo.pk, 2) and not menu.anexar_troca
    assert pacotes.itens_da_justificativa(emitido)[0].via is None


@pytest.mark.parametrize("revogada,arquivo,vale", [
    (False, "assinados/rs02.pdf", True), (True, "assinados/rs02.pdf", False),
    (False, "", False), (False, "  ", False),
])
def test_assinatura_exata_precisa_caminho_e_vigencia(
        cenario, emitido, revogada, arquivo, vale):
    ultimo = _novo(emitido, situacao="pronto")
    via = _via(ultimo, cenario.usuarios["operador"], revogada=revogada, arquivo=arquivo)
    anotado = _anotado(emitido)
    assert bool(anotado.via_oficio) is vale
    assert (assinados.vigente(assinados.Alvo("oficio", emitido)) is not None) is vale
    assert policies.menu_do_oficio(cenario.usuarios["operador"], anotado).anexar_troca is vale
    selecionada = pacotes.itens_da_justificativa(emitido)[0].via
    assert (selecionada.pk if selecionada else None) == (via.pk if vale else None)


def test_projecao_explicita_e_anotacoes_concordam_sem_sql(
        cenario, emitido, django_assert_num_queries):
    ultimo = _novo(emitido, situacao="pronto", justificativa="Convite tardio.")
    _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _via(ultimo, cenario.usuarios["operador"])
    documentos = list(emitido.documentos.all())
    vias = list(emitido.vias_assinadas.all())
    anotado = _anotado(emitido)
    with django_assert_num_queries(0):
        projecao = projetar_documentos(emitido, documentos=documentos, vias=vias)
        direto = policies.menu_do_oficio(cenario.usuarios["operador"], emitido, projecao=projecao)
        lista = policies.menu_do_oficio(cenario.usuarios["operador"], anotado)
    assert direto == lista


def test_vias_em_uma_consulta_sem_selecao_por_tipo(
        cenario, emitido, django_assert_num_queries):
    ultimo = _novo(emitido, situacao="pronto", justificativa="Convite tardio.")
    justificativa = _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _via(ultimo, cenario.usuarios["operador"])
    _via(justificativa, cenario.usuarios["operador"])
    with django_assert_num_queries(1):
        assert set(assinados.vigentes_do(emitido)) == {("oficio", ""), ("justificativa", "")}


def test_anexar_falha_sem_mutacao_quando_ultima_geracao_falhou(cenario, emitido):
    _novo(emitido, situacao="falhou")
    quantidade = Historico.objects.filter(oficio=emitido).count()
    with pytest.raises(assinados.ArquivoAssinadoInvalido, match="Gere o PDF"):
        assinados.anexar(cenario.usuarios["operador"], assinados.Alvo("oficio", emitido),
                         nome="via.pdf", conteudo=b"%PDF-1.4\n%%EOF\n")
    assert not emitido.vias_assinadas.exists()
    assert Historico.objects.filter(oficio=emitido).count() == quantidade


def test_leitor_nao_ganha_permissao_de_anexar(cenario, emitido):
    with pytest.raises(PermissionDenied):
        assinados.anexar(cenario.usuarios["consulta"], assinados.Alvo("oficio", emitido),
                         nome="via.pdf", conteudo=b"%PDF-1.4\n%%EOF\n")
    assert not emitido.vias_assinadas.exists()


@pytest.mark.parametrize("perfil,status", [("consulta", 200), ("operador", 200),
                                         ("gestor", 200), ("outra", 404)])
def test_docx_preserva_leitura_e_escopo(
        cenario, emitido, client, monkeypatch, perfil, status):
    monkeypatch.setattr("gestao.viagens.documentos.docx.docx_do_html", lambda *a, **kw: b"DOCX")
    client.force_login(cenario.usuarios[perfil])
    resposta = client.get(reverse("viagens:baixar_docx", args=[emitido.pk, "oficio"]))
    assert resposta.status_code == status


def test_docx_pronto_sem_pdf_usa_snapshot(emitido, cenario, client, monkeypatch):
    ultimo = _novo(emitido, situacao="pronto", arquivo="")
    observados = []

    def observar(tipo, dados):
        observados.append(dados)
        return "snapshot"

    monkeypatch.setattr(views, "html_do_documento", observar)
    monkeypatch.setattr("gestao.viagens.documentos.docx.docx_do_html", lambda *a, **kw: b"DOCX")
    client.force_login(cenario.usuarios["consulta"])
    resposta = client.get(reverse("viagens:baixar_docx", args=[emitido.pk, "oficio"]))
    assert resposta.status_code == 200 and "-v2.docx" in resposta["Content-Disposition"]
    assert observados == [ultimo.dados]
    assert assinados.documento_emitido(emitido, "oficio") is None
    item = pacotes.itens_da_justificativa(emitido)[0]
    assert item.estado == "PDF indisponível"
    assert item.docx() == b"DOCX"
    with pytest.raises(pacotes.PacoteInvalido, match="indisponível"):
        item.pdf()


def test_docx_lido_usa_snapshot_apos_alteracao_viva_e_nao_escreve(
        cenario, emitido, client, monkeypatch):
    ultimo = _novo(emitido, situacao="pronto")
    congelado = deepcopy(ultimo.dados)
    emitido.motivo = "Cadastro alterado após a emissão."
    emitido.save(update_fields=["motivo"])
    lidos = []

    def ler(tipo, dados):
        lidos.append(deepcopy(dados))
        return "snapshot"

    monkeypatch.setattr(views, "html_do_documento", ler)
    monkeypatch.setattr("gestao.viagens.documentos.docx.docx_do_html", lambda *a, **kw: b"DOCX")
    client.force_login(cenario.usuarios["consulta"])
    antes = Oficio.objects.filter(pk=emitido.pk).values().get()
    documentos = list(emitido.documentos.values())
    historico = Historico.objects.filter(oficio=emitido).count()
    mensagens = MensagemOutbox.objects.count()
    resposta = client.get(reverse("viagens:baixar_docx", args=[emitido.pk, "oficio"]))
    assert resposta.status_code == 200
    assert lidos == [congelado]
    assert Oficio.objects.filter(pk=emitido.pk).values().get() == antes
    assert list(emitido.documentos.values()) == documentos
    assert Historico.objects.filter(oficio=emitido).count() == historico
    assert MensagemOutbox.objects.count() == mensagens


def test_reaberto_tem_minuta_e_documentos_apenas_no_historico(cenario, emitido):
    services_usuario = cenario.usuarios["gestor"]
    services.reabrir(emitido, services_usuario, "Corrigir a viagem.")
    emitido.refresh_from_db()
    menu = policies.menu_do_oficio(services_usuario, _anotado(emitido))
    assert menu.minuta and menu.pdf is None
    assert assinados.documento_emitido(emitido, "oficio") is None
    assert pacotes.itens_da_justificativa(emitido)[0].estado == "Minuta"


def test_arquivo_nao_muda_identidade_mas_bloqueia_anexacao(cenario, emitido):
    ultimo = _novo(emitido, situacao="pronto")
    emitido.arquivado_em = timezone.now()
    emitido.save(update_fields=["arquivado_em"])
    menu = policies.menu_do_oficio(cenario.usuarios["operador"], _anotado(emitido))
    assert menu.pdf == (ultimo.pk, 2)
    assert menu.anexar == "inativo" and "Desarquive" in menu.anexar_motivo


def test_cancelado_preserva_pdf_exato_e_via_revogada(
        cenario, emitido, client, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    documento = emitido.documentos.get(tipo="oficio", versao=1)
    documento.arquivo.save("original.pdf", ContentFile(b"%PDF-original"))
    via = _via(documento, cenario.usuarios["operador"], revogada=True)
    via.arquivo.save("revogada.pdf", ContentFile(b"%PDF-revogada"))
    _novo(emitido, situacao="falhou")
    emitido.situacao = "cancelado"
    emitido.motivo_cancelamento = "Evento cancelado."
    emitido.save(update_fields=["situacao", "motivo_cancelamento"])
    assert queries.pdf_corrente_da_lista(_anotado(emitido), "oficio") is None
    client.force_login(cenario.usuarios["consulta"])
    original = client.get(reverse("viagens:baixar_documento", args=[documento.pk]),
                          {"versao": "original"})
    assert original.status_code == 200
    assert b"".join(original.streaming_content) == b"%PDF-original"
    historica = client.get(reverse("viagens:abrir_via_assinada", args=[via.pk]))
    assert historica.status_code == 200
    assert b"".join(historica.streaming_content) == b"%PDF-revogada"


def test_lista_justificativas_nao_oferece_pdf_historico_como_corrente(
        cenario, emitido, client):
    emitido.justificativa = "Texto vivo preenchido."
    emitido.save(update_fields=["justificativa"])
    antiga = _novo(emitido, tipo="justificativa", versao=1, situacao="pronto")
    _novo(emitido, situacao="pronto", justificativa="")
    client.force_login(cenario.usuarios["consulta"])
    resposta = client.get(reverse("viagens:justificativas"), {"aba": "preenchidas"})
    assert resposta.status_code == 200
    assert reverse("viagens:baixar_documento", args=[antiga.pk]) not in resposta.content.decode()


def test_lista_preserva_orcamento_19_e_exportacao_12(
        cenario, client, django_assert_max_num_queries):
    client.force_login(cenario.usuarios["operador"])
    with django_assert_max_num_queries(19):
        assert client.get(reverse("viagens:oficios")).status_code == 200
    with django_assert_max_num_queries(12):
        assert client.get(reverse("viagens:exportar_oficios")).status_code == 200


@pytest.mark.parametrize("quantidade", [20, 200])
def test_lista_crescida_preserva_orcamento_20(
        cenario, client, quantidade, django_assert_max_num_queries):
    usuario = cenario.usuarios["operador"]
    for _ in range(quantidade - 4):
        services.criar_rascunho(usuario)
    client.force_login(usuario)
    with django_assert_max_num_queries(20):
        assert client.get(reverse("viagens:oficios"), {"q": "a"}).status_code == 200
