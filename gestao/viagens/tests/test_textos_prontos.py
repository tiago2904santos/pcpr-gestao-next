"""Textos prontos: catálogo (serviço e tela) e uso na folha do ofício.

Paridade com os catálogos de motivo e de modelo de justificativa da referência
(docs/migration/oficios.md): nome, texto, ordem, ativo, um padrão por tipo; escolher o
modelo preenche o texto; o ofício novo nasce com o motivo padrão.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.urls import reverse

from gestao.cadastros import textos
from gestao.cadastros.models import ModeloTexto
from gestao.viagens import services
from gestao.viagens.models import Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)
MOTIVO = ModeloTexto.Tipo.MOTIVO


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def operador(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    return client


class TestServico:
    def test_cria_normaliza_e_recusa_nome_repetido(self, cenario):
        u = cenario.usuarios["operador"]
        t = textos.salvar(u, tipo=MOTIVO, nome="  Feira   regional ", texto=" Apoio na feira. ")
        assert (t.nome, t.texto, t.ordem) == ("Feira regional", "Apoio na feira.", 100)
        with pytest.raises(textos.TextoInvalido, match="Já existe"):
            textos.salvar(u, tipo=MOTIVO, nome="feira regional", texto="Outro")
        with pytest.raises(textos.TextoInvalido, match="nome"):
            textos.salvar(u, tipo=MOTIVO, nome=" ", texto="x")

    def test_um_padrao_por_tipo(self, cenario):
        u = cenario.usuarios["gestor"]
        a = textos.salvar(u, tipo=MOTIVO, nome="A", texto="Texto A")
        b = textos.salvar(u, tipo=MOTIVO, nome="B", texto="Texto B")
        textos.definir_padrao(u, a.pk)
        textos.definir_padrao(u, b.pk)
        a.refresh_from_db()
        assert not a.padrao and textos.padrao(MOTIVO).pk == b.pk
        # O banco também garante (não depende só do serviço).
        with pytest.raises(IntegrityError), transaction.atomic():
            ModeloTexto.objects.filter(pk=a.pk).update(padrao=True)

    def test_desativar_tira_da_escolha_e_do_padrao(self, cenario):
        u = cenario.usuarios["gestor"]
        t = textos.salvar(u, tipo=MOTIVO, nome="Velho", texto="Texto velho")
        textos.definir_padrao(u, t.pk)
        textos.alternar_ativo(u, t.pk)
        t.refresh_from_db()
        assert not t.ativo and not t.padrao
        assert t not in textos.opcoes(MOTIVO)
        with pytest.raises(textos.TextoInvalido, match="Reative"):
            textos.definir_padrao(u, t.pk)

    def test_ordem_define_a_escolha(self, cenario):
        u = cenario.usuarios["operador"]
        textos.salvar(u, tipo=MOTIVO, nome="Zebra", texto="z", ordem=1)
        assert textos.opcoes(MOTIVO)[0].nome == "Zebra"

    def test_padrao_e_textos_do_sistema_sao_do_gestor(self, cenario):
        """O padrão entra no ofício novo de todas as unidades: o operador não o escolhe nem
        altera; textos do sistema também são só do gestor (revisão de segurança)."""
        operador, gestor = cenario.usuarios["operador"], cenario.usuarios["gestor"]
        comum = textos.salvar(operador, tipo=MOTIVO, nome="Comum", texto="c")
        with pytest.raises(PermissionDenied):
            textos.definir_padrao(operador, comum.pk)
        textos.definir_padrao(gestor, comum.pk)
        with pytest.raises(PermissionDenied):  # agora é o padrão
            textos.salvar(operador, pk=comum.pk, tipo=MOTIVO, nome="Comum", texto="trocado")
        with pytest.raises(PermissionDenied):
            textos.alternar_ativo(operador, comum.pk)
        sistema = ModeloTexto.objects.create(tipo=MOTIVO, nome="Sis2", texto="s",
                                             padrao_sistema=True)
        with pytest.raises(PermissionDenied):
            textos.salvar(operador, pk=sistema.pk, tipo=MOTIVO, nome="Sis2", texto="x")
        with pytest.raises(textos.TextoInvalido):  # remover do editor: nunca os do sistema
            textos.desativar(gestor, sistema.pk)

    def test_desativar_e_idempotente(self, cenario):
        u = cenario.usuarios["operador"]
        t = textos.salvar(u, tipo=MOTIVO, nome="Duplo", texto="d")
        textos.desativar(u, t.pk)
        textos.desativar(u, t.pk)  # segundo clique não reativa
        t.refresh_from_db()
        assert not t.ativo

    def test_permissoes(self, cenario):
        consulta, operador = cenario.usuarios["consulta"], cenario.usuarios["operador"]
        with pytest.raises(PermissionDenied):
            textos.salvar(consulta, tipo=MOTIVO, nome="X", texto="Y")
        t = textos.salvar(operador, tipo=MOTIVO, nome="X", texto="Y")
        with pytest.raises(PermissionDenied):  # excluir é do gestor
            textos.excluir(operador, t.pk)
        assert textos.excluir(cenario.usuarios["gestor"], t.pk) == "X"
        sistema = ModeloTexto.objects.create(tipo=MOTIVO, nome="Sis", texto="s",
                                             padrao_sistema=True)
        with pytest.raises(PermissionDenied):
            textos.excluir(cenario.usuarios["gestor"], sistema.pk)


class TestTela:
    def test_lista_por_tipo_com_busca(self, operador):
        r = operador.get(reverse("cadastros:textos") + "?tipo=motivo")
        html = r.content.decode()
        assert r.status_code == 200 and "Unidade móvel em evento" in html
        assert "Novo texto pronto" in html
        r = operador.get(reverse("cadastros:textos") + "?tipo=motivo&q=inexistente")
        assert "Nenhum texto encontrado" in r.content.decode()

    def test_criar_editar_e_erro_reabre_a_janela(self, operador):
        url = reverse("cadastros:salvar_texto")
        r = operador.post(url, {"tipo": "motivo", "nome": "Feira", "ordem": 5,
                                "texto": "Apoio na feira."})
        assert r.status_code == 302 and "tipo=motivo" in r["Location"]
        t = ModeloTexto.objects.get(nome="Feira")
        r = operador.post(url, {"pk": t.pk, "tipo": "motivo", "nome": "Feira 2", "ordem": 5,
                                "texto": "Apoio."})
        t.refresh_from_db()
        assert t.nome == "Feira 2"
        r = operador.post(url, {"tipo": "motivo", "nome": "", "ordem": 5, "texto": ""})
        assert r.status_code == 422 and "data-abrir-ao-carregar" in r.content.decode()

    def test_guardar_pela_folha_responde_json(self, operador):
        r = operador.post(reverse("cadastros:salvar_texto"),
                          {"tipo": "justificativa", "nome": "Urgência", "ordem": 100,
                           "texto": "Convocação recebida fora do prazo."},
                          HTTP_ACCEPT="application/json")
        corpo = r.json()
        assert r.status_code == 200 and corpo["nome"] == "Urgência"
        assert ModeloTexto.objects.get(pk=corpo["id"]).tipo == "justificativa"
        r = operador.post(reverse("cadastros:salvar_texto"),
                          {"tipo": "justificativa", "nome": "", "ordem": 100, "texto": "x"},
                          HTTP_ACCEPT="application/json")
        assert r.status_code == 422 and r.json()["erro"]

    def test_consulta_ve_mas_nao_gerencia(self, client, cenario):
        client.force_login(cenario.usuarios["consulta"])
        assert client.get(reverse("cadastros:textos")).status_code == 403  # sem view_modelotexto
        assert client.post(reverse("cadastros:salvar_texto"),
                           {"tipo": "motivo", "nome": "X", "texto": "Y"}).status_code == 403

    def test_pk_invalido_e_404(self, operador):
        r = operador.post(reverse("cadastros:salvar_texto"),
                          {"pk": "abc", "tipo": "motivo", "nome": "X", "texto": "Y"})
        assert r.status_code == 404

    def test_acoes_da_linha(self, client, cenario):
        client.force_login(cenario.usuarios["gestor"])
        t = ModeloTexto.objects.create(tipo=MOTIVO, nome="Linha", texto="Texto da linha")
        client.post(reverse("cadastros:texto_padrao", args=[t.pk]))
        t.refresh_from_db()
        assert t.padrao
        client.post(reverse("cadastros:texto_ativo", args=[t.pk]))
        t.refresh_from_db()
        assert not t.ativo and not t.padrao
        client.post(reverse("cadastros:texto_excluir", args=[t.pk]))
        assert not ModeloTexto.objects.filter(pk=t.pk).exists()


class TestNaFolhaDoOficio:
    def test_escolha_traz_o_texto_e_o_atalho(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        assert 'data-texto-pronto data-alvo="id_motivo"' in html
        assert 'data-texto="Apoio e condução da Unidade Móvel no evento."' in html
        assert "Guardar texto" in html and 'id="dialogo-guardar-texto"' in html
        # A justificativa usa o mesmo componente (o cartão só aparece quando o prazo pede).
        com_prazo = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
        html = operador.get(reverse("viagens:editar", args=[com_prazo.pk])).content.decode()
        assert 'data-texto-pronto data-alvo="id_justificativa"' in html

    def test_sem_js_escolher_com_motivo_vazio_preenche(self, operador, cenario):
        from .test_views import _post_edicao

        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        modelo = ModeloTexto.objects.get(tipo=MOTIVO, nome="Unidade móvel em evento")
        operador.post(reverse("viagens:editar", args=[oficio.pk]),
                      _post_edicao(oficio, motivo="", motivo_modelo=modelo.pk))
        oficio.refresh_from_db()
        assert oficio.motivo == modelo.texto

    def test_oficio_novo_nasce_com_o_motivo_padrao(self, cenario):
        u = cenario.usuarios["operador"]
        modelo = ModeloTexto.objects.get(tipo=MOTIVO, nome="Unidade móvel em evento")
        assert services.criar_rascunho(u).motivo == ""  # sem padrão, nasce vazio
        textos.definir_padrao(cenario.usuarios["gestor"], modelo.pk)
        assert services.criar_rascunho(u).motivo == modelo.texto
