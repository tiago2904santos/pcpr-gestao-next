"""RS-01: leitura autorizada, fonte histórica e integração aos contextos existentes."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor
from gestao.plataforma.models import MensagemOutbox
from gestao.viagens import services, views
from gestao.viagens.forms import FormularioOficio
from gestao.viagens.models import Documento, Historico, Oficio, Trecho

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture(autouse=True)
def projecao_sem_consultas(monkeypatch, django_assert_num_queries):
    """As views devem fornecer todas as relações; o adaptador não pode ler o banco."""
    projetar = views.projetar_dados_eprotocolo

    def observar(oficio, **listas):
        assert all(listas.get(chave) is not None for chave in (
            "documentos", "viajantes", "trechos"))
        with django_assert_num_queries(0):
            return projetar(oficio, **listas)

    monkeypatch.setattr(views, "projetar_dados_eprotocolo", observar)


def _campos(copia):
    assert copia.disponivel
    return {campo.rotulo: campo.valor for campo in copia.dados.campos}


def _bloco(resposta):
    encontrado = re.search(
        r"<details[^>]*data-dados-eprotocolo.*?</details>", resposta.content.decode(), re.S)
    assert encontrado is not None
    return encontrado.group()


def _dados_formulario(oficio):
    dados = {chave: valor for chave, valor in FormularioOficio(instance=oficio).initial.items()
             if valor is not None and valor is not False}
    dados.update({"versao": oficio.versao, "sede-uf": oficio.sede.uf,
                  "sede-cidade": str(oficio.sede), "destino-TOTAL_FORMS": "0",
                  "destino-INITIAL_FORMS": "0", "destino-MIN_NUM_FORMS": "1",
                  "destino-MAX_NUM_FORMS": "10"})
    return dados


@pytest.mark.parametrize("perfil", ["consulta", "operador", "gestor"])
def test_resumo_permite_copia_ao_leitor_autorizado(client, cenario, perfil):
    client.force_login(cenario.usuarios[perfil])
    resposta = client.get(reverse("viagens:resumo", args=[cenario.ids["oficio_emitido"]]))
    assert resposta.status_code == 200
    assert resposta.context["copia"].fonte == "emissao"
    assert 'id="eprotocolo-resumo-1"' in _bloco(resposta)
    assert "Copiar tudo" in _bloco(resposta)


@pytest.mark.parametrize("rota", ["editar", "resumo"])
def test_copia_respeita_escopo_da_unidade(client, cenario, rota):
    client.force_login(cenario.usuarios["operador"])
    resposta = client.get(reverse(f"viagens:{rota}", args=[cenario.ids["oficio_outra_unidade"]]))
    assert resposta.status_code == 404
    assert "data-dados-eprotocolo" not in resposta.content.decode()


def test_copiar_nao_concede_permissao_de_emitir(client, cenario):
    client.force_login(cenario.usuarios["consulta"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    antes = oficio.versao
    resposta = client.post(reverse("viagens:emitir", args=[oficio.pk]), {"versao": antes})
    assert resposta.status_code == 403
    oficio.refresh_from_db()
    assert oficio.situacao == Oficio.Situacao.RASCUNHO
    assert oficio.versao == antes


@pytest.mark.parametrize("rota,revisar", [("resumo", False), ("editar", False), ("editar", True)])
def test_get_com_copia_nao_escreve_negocio(client, cenario, rota, revisar):
    client.force_login(cenario.usuarios["operador"])
    pk = cenario.ids["oficio_rascunho"]
    antes = Oficio.objects.filter(pk=pk).values().get()
    historico = Historico.objects.filter(oficio_id=pk).count()
    documentos = list(Documento.objects.filter(oficio_id=pk).values())
    outbox = MensagemOutbox.objects.count()
    resposta = client.get(reverse(f"viagens:{rota}", args=[pk]),
                          {"revisar": "1"} if revisar else {})
    assert resposta.status_code == 200
    assert "data-dados-eprotocolo" in resposta.content.decode()
    assert Oficio.objects.filter(pk=pk).values().get() == antes
    assert Historico.objects.filter(oficio_id=pk).count() == historico
    assert list(Documento.objects.filter(oficio_id=pk).values()) == documentos
    assert MensagemOutbox.objects.count() == outbox


def test_emitido_copia_snapshot_apos_renomear_cadastros(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    documento = oficio.documentos.get(tipo=Documento.Tipo.OFICIO)
    snapshot = deepcopy(documento.dados)
    antes = client.get(reverse("viagens:resumo", args=[oficio.pk])).context["copia"].dados
    for servidor in Servidor.objects.filter(viagens__oficio=oficio):
        Servidor.objects.filter(pk=servidor.pk).update(
            nome=f"Nome atual após emissão {servidor.pk}")
    destinos = oficio.trechos.exclude(destino_id=oficio.sede_id).values("destino_id")
    Municipio.objects.filter(pk__in=destinos).update(nome="Destino atual após emissão")
    resposta = client.get(reverse("viagens:resumo", args=[oficio.pk]))
    assert resposta.status_code == 200
    assert resposta.context["copia"].dados == antes
    bloco = _bloco(resposta)
    assert "Nome atual após emissão" not in bloco
    assert "Destino atual após emissão" not in bloco
    for viajante in snapshot["viajantes"]:
        assert viajante["nome"] in bloco
        assert viajante["cpf"] not in bloco
        assert viajante["rg"] not in bloco
    documento.refresh_from_db()
    assert documento.dados == snapshot


@pytest.mark.parametrize("situacao", [Documento.Situacao.GERANDO, Documento.Situacao.FALHOU])
def test_resumo_copia_maior_versao_mesmo_sem_pdf_pronto(client, cenario, situacao):
    client.force_login(cenario.usuarios["operador"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    anterior = oficio.documentos.get(tipo=Documento.Tipo.OFICIO)
    Documento.objects.filter(pk=anterior.pk).update(situacao="pronto", sha256="a" * 64)
    snapshot = deepcopy(anterior.dados)
    snapshot["motivo"] = "Motivo da segunda emissão"
    atual = Documento.objects.create(
        oficio=oficio, tipo="oficio", versao=2, situacao=situacao,
        dados=snapshot, emitido_por=cenario.usuarios["operador"],
        erro="Falha de geração" if situacao == Documento.Situacao.FALHOU else "")
    resposta = client.get(reverse("viagens:resumo", args=[oficio.pk]))
    copia = resposta.context["copia"]
    assert copia.versao == atual.versao == 2
    assert copia.situacao_documento == situacao
    assert "Motivo da segunda emissão" in _campos(copia)["Detalhamento"]
    assert "Dados da emissão v2" in _bloco(resposta)
    assert resposta.context["pdf_oficio"] is None


def test_snapshot_invalido_nao_reconstroi_com_cadastros_vivos(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    pk = cenario.ids["oficio_emitido"]
    Documento.objects.filter(oficio_id=pk).update(dados={})
    resposta = client.get(reverse("viagens:resumo", args=[pk]))
    assert resposta.status_code == 200
    assert not resposta.context["copia"].disponivel
    assert "Os dados desta emissão estão indisponíveis" in _bloco(resposta)
    assert "data-copiar-alvo" not in _bloco(resposta)


def test_revisao_copia_assunto_da_data_efetiva_sem_gravar(client, monkeypatch):
    referencia = date(2026, 10, 7)
    localdate_real = timezone.localdate

    def dia_local(value=None, timezone=None):
        return referencia if value is None else localdate_real(value, timezone)

    monkeypatch.setattr(timezone, "localdate", dia_local)
    cenario = cenario_completo(hoje=referencia)
    client.force_login(cenario.usuarios["operador"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    original = referencia - timedelta(days=2)
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio=original, data_oficio_manual=False)
    for trecho in oficio.trechos.all():
        Trecho.objects.filter(pk=trecho.pk).update(
            saida_em=trecho.saida_em - timedelta(days=3),
            chegada_em=trecho.chegada_em - timedelta(days=3))
    resposta = client.get(reverse("viagens:editar", args=[oficio.pk]), {"revisar": "1"})
    assert resposta.status_code == 200
    folha = _campos(resposta.context["copia"])
    revisao = _campos(resposta.context["resumo"]["copia"])
    assert "autorização" in folha["Assunto"]
    assert "convalidação" in revisao["Assunto"]
    html = resposta.content.decode()
    assert 'id="eprotocolo-folha-1"' in html
    assert 'id="eprotocolo-resumo-1"' in html
    assert "Dados para a emissão revisada" in html
    oficio.refresh_from_db()
    assert oficio.data_oficio == original


def test_erro_de_roteiro_com_form_valido_nao_copia_instance_mutada(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    original = oficio.motivo
    dados = _dados_formulario(oficio)
    dados.update({"motivo": "Texto digitado ainda não salvo", "destino-TOTAL_FORMS": "1",
                  "destino-0-cidade": "Município inexistente", "destino-0-uf": "PR"})
    resposta = client.post(reverse("viagens:editar", args=[oficio.pk]), dados)
    assert resposta.status_code == 422
    assert resposta.context["form"].is_valid()
    assert resposta.context["oficio"].motivo == "Texto digitado ainda não salvo"
    assert not resposta.context["copia"].disponivel
    assert "Salve o rascunho antes de copiar" in _bloco(resposta)
    assert "data-copiar-alvo" not in _bloco(resposta)
    oficio.refresh_from_db()
    assert oficio.motivo == original


def test_previa_de_roteiro_nao_promete_copia_salva(client, cenario):
    usuario = cenario.usuarios["operador"]
    client.force_login(usuario)
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    versao = oficio.versao
    roteiro = services.salvar_roteiro(
        usuario, None, {"quantidade_servidores": 1, "sede": oficio.sede},
        services.trechos_informados_do_roteiro_de(oficio))
    dados = _dados_formulario(oficio)
    dados.update({"acao": "usar_roteiro", "roteiro_modelo": roteiro.pk})
    resposta = client.post(reverse("viagens:editar", args=[oficio.pk]), dados)
    assert resposta.status_code == 200
    assert resposta.context["previa_diarias"]
    assert not resposta.context["copia"].disponivel
    assert "Salve o rascunho antes de copiar" in _bloco(resposta)
    assert "data-copiar-alvo" not in _bloco(resposta)
    oficio.refresh_from_db()
    assert oficio.roteiro_id is None
    assert oficio.versao == versao


@pytest.mark.parametrize("acao", ["adicionar", "remover", "motorista"])
def test_equipe_htmx_atualiza_copia_fora_de_banda(client, cenario, acao):
    client.force_login(cenario.usuarios["operador"])
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    viajante = oficio.viajantes.get()
    if acao == "adicionar":
        servidor = Servidor.objects.filter(unidade_id=oficio.unidade_id).exclude(
            pk=viajante.servidor_id).first()
        assert servidor is not None
        url = reverse("viagens:adicionar_viajante", args=[oficio.pk])
        dados = {"id": servidor.pk}
    elif acao == "remover":
        url = reverse("viagens:remover_viajante", args=[oficio.pk, viajante.pk])
        dados = {}
    else:
        url = reverse("viagens:definir_motorista", args=[oficio.pk])
        dados = {"viajante": viajante.pk}
    resposta = client.post(url, dados, HTTP_HX_REQUEST="true")
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert 'id="dados-eprotocolo-folha" data-vivo hx-swap-oob="outerHTML"' in html
    nomes = _campos(resposta.context["copia"])["Interessados"]
    if acao == "adicionar":
        assert servidor.nome in nomes
    elif acao == "remover":
        assert viajante.servidor.nome not in nomes
    else:
        assert viajante.servidor.nome in nomes
