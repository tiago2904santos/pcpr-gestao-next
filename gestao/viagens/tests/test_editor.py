"""Editor de documento no visualizador (ADR 0018): regiões, serviços, visões e emissão."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import ModeloTexto
from gestao.viagens import services
from gestao.viagens.documentos import regioes as reg
from gestao.viagens.documentos.dados import dados_do_oficio
from gestao.viagens.documentos.pdf import html_do_documento, regioes_do_modelo
from gestao.viagens.models import Documento, EdicaoDocumento, Historico, Oficio

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def operador(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    return client


@pytest.fixture
def rascunho(cenario):
    return Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])


def _json(cliente, url, corpo, metodo="post"):
    return getattr(cliente, metodo)(url, data=json.dumps(corpo), content_type="application/json")


# ---------------------------------------------------------------- regiões (texto puro)
class TestRegioes:
    HTML = (
        '<div data-regiao="corpo"><!--[regiao:corpo]-->'
        '<p data-bloco="a" data-rotulo="Saudação">'
        'Olá <span data-campo="motivo" data-rotulo="Motivo" data-obrigatorio>x</span></p>'
        '<div class="quebra" data-quebra="q"></div>'
        '<table data-bloco="b" data-rotulo="Equipe"><tr><td>1</td></tr></table>'
        "<!--[/regiao:corpo]--></div>"
    )

    def test_extrai_e_aplica_regioes(self):
        r = reg.extrair_regioes(self.HTML)
        assert list(r) == ["corpo"] and r["corpo"].startswith('<p data-bloco="a"')
        novo = reg.aplicar_regioes(self.HTML, {"corpo": "<p>novo</p>"})
        assert reg.extrair_regioes(novo) == {"corpo": "<p>novo</p>"}
        # região desconhecida não altera nada
        assert reg.aplicar_regioes(self.HTML, {"outra": "x"}) == self.HTML

    def test_saneador_mantem_texto_e_descarta_marcacao_estranha(self):
        sujo = (
            "<script>alert(1)</script>"
            '<p onclick="x()" style="color:red" class="centro x" id="i">'
            'a &amp; b<img src=x onerror=1></p><p style="text-align: center">c</p><br/>'
            '<iframe src="x"></iframe>'
        )
        assert reg.sanear_html(sujo) == (
            '<p class="centro">a &amp; b</p><p style="text-align: center">c</p><br>'
        )

    def test_saneador_mantem_marcas_do_documento(self):
        corpo = reg.extrair_regioes(self.HTML)["corpo"]
        assert reg.sanear_html(corpo) == corpo

    def test_blocos_alterados_por_texto_quebra_e_remocao(self):
        corpo = reg.extrair_regioes(self.HTML)["corpo"]
        editado = corpo.replace("Olá", "Oi").replace(
            'class="quebra"', 'class="quebra quebra--ativa"'
        )
        assert reg.blocos_alterados(corpo, editado) == [
            {"chave": "a", "rotulo": "Saudação"},
            {"chave": "quebras", "rotulo": "Quebras de página"},
        ]
        sem_tabela = corpo[: corpo.index("<table")]
        assert reg.blocos_alterados(corpo, sem_tabela) == [
            {"chave": "b", "rotulo": "Equipe (removido)"}
        ]
        assert reg.blocos_alterados(corpo, corpo) == []

    def test_campos_vinculados_sao_reescritos_e_detectados(self):
        html = reg.sincronizar_campos(self.HTML, {"motivo": "a <b>\nc"})
        assert (
            '<span data-campo="motivo" data-rotulo="Motivo" data-obrigatorio>a &lt;b&gt;\nc</span>'
        ) in html
        assert reg.campos_presentes(html) == {"motivo"}
        multilinha = self.HTML.replace("data-obrigatorio>", "data-obrigatorio data-multilinha>")
        assert "a<br>c" in reg.sincronizar_campos(multilinha, {"motivo": "a\nc"})

    def test_bloco_original_e_marcacao_de_alterados(self):
        corpo = reg.extrair_regioes(self.HTML)["corpo"]
        assert reg.bloco_original(corpo, "b").startswith("<table")
        assert reg.bloco_original(corpo, "zz") is None
        marcado = reg.marcar_blocos_alterados(corpo, {"a"})
        assert '<p data-bloco="a" data-rotulo="Saudação" class="bloco--alterado">' in marcado


# ---------------------------------------------------------------- modelos marcados
class TestModelosMarcados:
    def test_oficio_e_justificativa_tem_regioes_blocos_e_campos(self, rascunho):
        dados = dados_do_oficio(rascunho)
        oficio = regioes_do_modelo("oficio", dados)
        assert list(oficio) == ["cabecalho", "corpo", "rodape"]
        assert reg.campos_presentes(oficio["cabecalho"]) == {"data_oficio", "protocolo"}
        assert reg.campos_presentes(oficio["corpo"]) == {"motivo"}
        assert {e.chave for e in reg.elementos_marcados(oficio["corpo"])} >= {
            "saudacao",
            "equipe",
            "resumo",
            "roteiro",
            "transporte",
            "custos",
            "motivo",
            "declaracao",
        }
        just = regioes_do_modelo("justificativa", dados)
        assert list(just) == ["corpo", "rodape"]
        assert reg.campos_presentes(just["corpo"]) == {"justificativa"}

    def test_html_final_aplica_regiao_editada_e_mantem_campo_vivo(self, rascunho):
        dados = dados_do_oficio(rascunho)
        original = regioes_do_modelo("oficio", dados)["corpo"]
        editado = original.replace("conforme cronograma abaixo", "conforme o cronograma a seguir")
        dados["motivo"] = "Motivo atualizado depois da edição"
        html = html_do_documento("oficio", dados, regioes={"corpo": editado})
        assert "conforme o cronograma a seguir" in html
        assert "Motivo atualizado depois da edição" in html  # o campo vinculado é sempre o atual

    def test_folha_e_pdf_usam_recursos_diferentes(self, rascunho):
        dados = dados_do_oficio(rascunho)
        pdf = html_do_documento("oficio", dados)
        folha = html_do_documento("oficio", dados, folha=True, nonce="abc")
        assert "file://" in pdf and "/static/documentos/" not in pdf and "folha.css" not in pdf
        assert "/static/documentos/" in folha and "folha.css" in folha
        assert '<style nonce="abc">' in folha


# ---------------------------------------------------------------- serviços
class TestServicosDeTexto:
    def _corpo_editado(self, oficio, trecho="com a urgência que o caso requer"):
        original = regioes_do_modelo("oficio", dados_do_oficio(oficio))
        return {
            **original,
            "corpo": original["corpo"].replace(
                "conforme cronograma abaixo:", f"conforme cronograma abaixo, {trecho}:"
            ),
        }

    def test_salvar_cria_versao_so_com_regioes_diferentes(self, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        e = services.salvar_texto_do_documento(
            rascunho, usuario, "oficio", self._corpo_editado(rascunho)
        )
        assert e.numero == 1 and e.acao == "editado" and list(e.regioes) == ["corpo"]
        assert e.blocos_alterados == [{"chave": "saudacao", "rotulo": "Saudação e pedido"}]
        assert set(e.impressoes) == {"corpo"}
        h = Historico.objects.filter(oficio=rascunho, acao=Historico.Acao.TEXTO).first()
        assert h is not None and "Saudação e pedido" in h.descricao

    def test_igual_ao_modelo_nao_cria_versao(self, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        original = regioes_do_modelo("oficio", dados_do_oficio(rascunho))
        with pytest.raises(services.RegraViolada):
            services.salvar_texto_do_documento(rascunho, usuario, "oficio", original)
        assert not EdicaoDocumento.objects.exists()

    def test_salvamentos_seguidos_da_mesma_pessoa_atualizam_a_versao(self, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        e1 = services.salvar_texto_do_documento(
            rascunho, usuario, "oficio", self._corpo_editado(rascunho)
        )
        e2 = services.salvar_texto_do_documento(
            rascunho, usuario, "oficio", self._corpo_editado(rascunho, "sem demora"), versao_base=1
        )
        assert e2.pk == e1.pk and "sem demora" in e2.regioes["corpo"]
        assert EdicaoDocumento.objects.count() == 1
        # Passada a janela, vira versão nova.
        EdicaoDocumento.objects.filter(pk=e1.pk).update(
            criado_em=timezone.now() - services.JANELA_DE_COALESCENCIA - timedelta(minutes=1)
        )
        e3 = services.salvar_texto_do_documento(
            rascunho, usuario, "oficio", self._corpo_editado(rascunho, "hoje"), versao_base=1
        )
        assert e3.numero == 2 and EdicaoDocumento.objects.count() == 2

    def test_outra_pessoa_gera_versao_nova_e_base_errada_conflita(self, rascunho, cenario):
        operador, gestor = cenario.usuarios["operador"], cenario.usuarios["gestor"]
        services.salvar_texto_do_documento(
            rascunho, operador, "oficio", self._corpo_editado(rascunho)
        )
        e2 = services.salvar_texto_do_documento(
            rascunho, gestor, "oficio", self._corpo_editado(rascunho, "agora"), versao_base=1
        )
        assert e2.numero == 2
        with pytest.raises(services.ConflitoDeEdicao):
            services.salvar_texto_do_documento(
                rascunho, operador, "oficio", self._corpo_editado(rascunho, "x"), versao_base=1
            )

    def test_campo_vinculado_nao_pode_sumir_do_texto(self, rascunho, cenario):
        regioes = self._corpo_editado(rascunho)
        corpo = regioes["corpo"]
        inicio = corpo.index('<span data-campo="motivo"')
        fim = corpo.index("</span>", inicio) + len("</span>")
        regioes["corpo"] = corpo[:inicio] + corpo[fim:]
        with pytest.raises(services.RegraViolada, match="Motivo da viagem"):
            services.salvar_texto_do_documento(
                rascunho, cenario.usuarios["operador"], "oficio", regioes
            )

    def test_restaurar_e_voltar_ao_modelo_acrescentam_versoes(self, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        services.salvar_texto_do_documento(
            rascunho, usuario, "oficio", self._corpo_editado(rascunho)
        )
        m = services.voltar_texto_ao_modelo(rascunho, usuario, "oficio")
        assert m is not None and m.numero == 2 and m.do_modelo and m.acao == "modelo"
        assert services.regioes_vigentes(rascunho, "oficio") == {}
        r = services.restaurar_texto_do_documento(rascunho, usuario, "oficio", 1)
        assert r.numero == 3 and r.acao == "restaurado" and r.restaurada_de.numero == 1
        assert "urgência" in services.regioes_vigentes(rascunho, "oficio")["corpo"]
        assert EdicaoDocumento.objects.count() == 3
        with pytest.raises(services.RegraViolada):
            services.restaurar_texto_do_documento(rascunho, usuario, "oficio", 99)

    def test_so_quem_edita_o_rascunho_edita_o_texto(self, cenario):
        from django.core.exceptions import PermissionDenied

        emitido = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        with pytest.raises(PermissionDenied):
            services.salvar_texto_do_documento(
                emitido, cenario.usuarios["operador"], "oficio", self._corpo_editado(emitido)
            )
        rascunho = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
        with pytest.raises(PermissionDenied):
            services.salvar_texto_do_documento(
                rascunho, cenario.usuarios["consulta"], "oficio", self._corpo_editado(rascunho)
            )

    def test_campo_vinculado_grava_no_oficio_com_versao(self, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        versao = rascunho.versao
        atual = services.salvar_campo_do_documento(
            rascunho, usuario, "motivo", "  Novo   motivo \r\nem duas linhas ", versao=versao
        )
        assert atual.motivo == "Novo   motivo \nem duas linhas" and atual.versao == versao + 1
        with pytest.raises(services.ConflitoDeEdicao):
            services.salvar_campo_do_documento(rascunho, usuario, "motivo", "x", versao=versao)
        atual = services.salvar_campo_do_documento(rascunho, usuario, "protocolo", "12.345.678-9")
        assert atual.protocolo == "123456789"
        with pytest.raises(services.RegraViolada, match="9 dígitos"):
            services.salvar_campo_do_documento(rascunho, usuario, "protocolo", "123")
        with pytest.raises(services.RegraViolada):
            services.salvar_campo_do_documento(rascunho, usuario, "inexistente", "x")

    def test_textos_prontos(self, cenario):
        usuario = cenario.usuarios["operador"]
        m = services.criar_texto_pronto(
            usuario, "oficio", "  Pedido  urgente ", "Texto\n\ndo pedido"
        )
        assert m.tipo == ModeloTexto.Tipo.OFICIO and m.nome == "Pedido urgente"
        assert m in services.textos_prontos("oficio") and m not in services.textos_prontos(
            "justificativa"
        )
        padrao = ModeloTexto.objects.create(
            tipo=ModeloTexto.Tipo.OFICIO, nome="Padrão", texto="x", padrao_sistema=True
        )
        with pytest.raises(services.RegraViolada):
            services.desativar_texto_pronto(usuario, padrao.pk)
        services.desativar_texto_pronto(usuario, m.pk)
        assert m not in services.textos_prontos("oficio")
        with pytest.raises(services.RegraViolada):
            services.criar_texto_pronto(usuario, "oficio", "", "")

    def test_emissao_congela_o_texto_editado_no_instantaneo(self, cenario):
        usuario = cenario.usuarios["operador"]
        pronto = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
        pronto = services.salvar_dados(
            pronto,
            usuario,
            {"protocolo": "123456789", "justificativa": "Convocação de última hora."},
        )
        e = services.salvar_texto_do_documento(
            pronto, usuario, "oficio", self._corpo_editado(pronto)
        )
        doc = services.emitir(pronto, usuario)
        assert doc.edicao_id == e.pk and doc.dados["edicao"]["numero"] == 1
        assert "urgência que o caso requer" in html_do_documento("oficio", doc.dados)
        # A edição vale para o ofício, não para a justificativa (regiões diferentes).
        for d in Documento.objects.filter(oficio=pronto).exclude(tipo="oficio"):
            assert d.edicao_id is None


# ---------------------------------------------------------------- visões
class TestVisoesDoEditor:
    def test_folha_html_com_nonce_e_moldura_da_propria_origem(self, operador, rascunho):
        r = operador.get(reverse("viagens:folha", args=[rascunho.pk, "oficio"]))
        assert r.status_code == 200 and r["Cache-Control"] == "no-store"
        csp = r["Content-Security-Policy"]
        assert "frame-ancestors 'self'" in csp and "'nonce-" in csp
        html = r.content.decode()
        assert 'data-regiao="corpo"' in html and 'data-campo="motivo"' in html
        assert "folha.css" in html and "<style nonce=" in html
        assert (
            operador.get(reverse("viagens:folha", args=[rascunho.pk, "outro"])).status_code == 404
        )

    def test_folha_de_oficio_de_outra_unidade_e_404(self, client, cenario):
        client.force_login(cenario.usuarios["outra"])
        r = client.get(reverse("viagens:folha", args=[cenario.ids["oficio_rascunho"], "oficio"]))
        assert r.status_code == 404

    def test_estado_salvar_restaurar_e_modelo(self, operador, rascunho, cenario):
        base = reverse("viagens:editor_estado", args=[rascunho.pk, "oficio"])
        e = operador.get(base).json()
        assert e["pode_editar"] and e["edicao"] is None and e["versoes"] == []
        assert {c["chave"] for c in e["campos"]} == {"data_oficio", "protocolo", "motivo"}
        original = regioes_do_modelo("oficio", dados_do_oficio(rascunho))
        corpo = original["corpo"].replace("conforme cronograma abaixo:", "conforme o cronograma:")
        r = _json(
            operador,
            reverse("viagens:editor_salvar", args=[rascunho.pk, "oficio"]),
            {"regioes": {"corpo": corpo}, "versao_base": 0},
        )
        assert r.status_code == 200 and r.json()["edicao"]["numero"] == 1
        assert r.json()["edicao"]["blocos_alterados"][0]["chave"] == "saudacao"
        # a folha vigente traz o texto editado e marca o bloco; a versão 0 é o modelo
        html = operador.get(reverse("viagens:folha", args=[rascunho.pk, "oficio"])).content.decode()
        assert "conforme o cronograma:" in html and 'class="bloco--alterado"' in html
        modelo = operador.get(reverse("viagens:folha", args=[rascunho.pk, "oficio"]) + "?versao=0")
        assert "conforme cronograma abaixo:" in modelo.content.decode()
        # base errada → 409 com o estado atual
        r = _json(
            operador,
            reverse("viagens:editor_salvar", args=[rascunho.pk, "oficio"]),
            {"regioes": {"corpo": corpo + "<p>x</p>"}, "versao_base": 7},
        )
        assert r.status_code == 409 and r.json()["conflito"]
        r = operador.post(reverse("viagens:editor_modelo", args=[rascunho.pk, "oficio"]))
        assert r.status_code == 200 and r.json()["edicao"]["do_modelo"]
        r = operador.post(reverse("viagens:editor_restaurar", args=[rascunho.pk, "oficio", 1]))
        assert r.status_code == 200 and r.json()["edicao"]["restaurada_de"] == 1
        assert len(r.json()["versoes"]) == 3

    def test_salvar_recusa_corpo_invalido_e_leitor(self, operador, rascunho, client, cenario):
        url = reverse("viagens:editor_salvar", args=[rascunho.pk, "oficio"])
        assert _json(operador, url, {"regioes": "x"}).status_code == 400
        client.force_login(cenario.usuarios["consulta"])
        original = regioes_do_modelo("oficio", dados_do_oficio(rascunho))
        r = _json(client, url, {"regioes": {"corpo": original["corpo"] + "<p>a</p>"}})
        assert r.status_code == 403

    def test_campo_vinculado_pela_folha(self, operador, rascunho):
        url = reverse("viagens:editor_campo", args=[rascunho.pk, "oficio", "motivo"])
        r = _json(
            operador,
            url,
            {"valor": "Motivo escrito na folha", "versao": rascunho.versao},
            metodo="patch",
        )
        assert r.status_code == 200
        assert r.json()["resultado"]["valor"] == "Motivo escrito na folha"
        assert r.json()["versao_oficio"] == rascunho.versao + 1
        assert not [p for p in r.json()["pendencias"] if p["chave"] == "motivo"]
        r = _json(operador, url, {"valor": "outro", "versao": rascunho.versao}, metodo="patch")
        assert r.status_code == 409
        r = _json(operador, url, {"valor": 5}, metodo="patch")
        assert r.status_code == 400

    def test_original_paginas_presenca_e_textos(self, operador, rascunho, cenario):
        args = [rascunho.pk, "oficio"]
        r = operador.get(reverse("viagens:editor_original", args=args) + "?bloco=saudacao")
        assert r.status_code == 200 and r.json()["html"].startswith('<p data-bloco="saudacao"')
        assert (
            operador.get(reverse("viagens:editor_original", args=args) + "?bloco=zz").status_code
            == 404
        )
        p = operador.get(reverse("viagens:editor_paginas", args=args)).json()
        assert p["total"] >= 1 and p["blocos"]["saudacao"] == 1
        assert operador.post(reverse("viagens:editor_presenca", args=args)).json() == {
            "presenca": []
        }
        # outra pessoa na mesma folha aparece para o operador
        gestor = cenario.usuarios["gestor"]
        from django.test import Client

        outro = Client()
        outro.force_login(gestor)
        outro.post(reverse("viagens:editor_presenca", args=args))
        assert operador.get(reverse("viagens:editor_estado", args=args)).json()["presenca"] == [
            {"nome": str(gestor)}
        ]
        r = _json(
            operador,
            reverse("viagens:editor_textos", args=args),
            {"nome": "Pedido", "texto": "Texto do pedido"},
        )
        assert r.status_code == 201 and r.json()["criado"]["nome"] == "Pedido"
        lista = operador.get(reverse("viagens:editor_textos", args=args)).json()["textos"]
        assert [t["nome"] for t in lista][-1:] == ["Pedido"] or any(
            t["nome"] == "Pedido" for t in lista
        )
        pk = r.json()["criado"]["id"]
        r = operador.post(reverse("viagens:editor_remover_texto", args=[*args, pk]))
        assert r.status_code == 200 and all(t["id"] != pk for t in r.json()["textos"])

    def test_estado_avisa_texto_desatualizado(self, operador, rascunho, cenario):
        usuario = cenario.usuarios["operador"]
        original = regioes_do_modelo("oficio", dados_do_oficio(rascunho))
        services.salvar_texto_do_documento(
            rascunho,
            usuario,
            "oficio",
            {"cabecalho": original["cabecalho"].replace("Data:", "Data do ofício:")},
        )
        services.salvar_dados(
            rascunho, usuario, {"data_oficio": rascunho.data_oficio + timedelta(days=1)}
        )
        e = operador.get(reverse("viagens:editor_estado", args=[rascunho.pk, "oficio"])).json()
        assert e["desatualizadas"] == ["cabecalho"]

    def test_folha_de_edicao_traz_o_editor(self, operador, rascunho):
        html = operador.get(reverse("viagens:editar", args=[rascunho.pk])).content.decode()
        assert "<pc-editor-documento" in html and "data-editavel" in html
        assert reverse("viagens:folha", args=[rascunho.pk, "oficio"]) in html
        assert "css/editor.css" in html

    def test_orcamento_de_consultas_do_estado(
        self, operador, rascunho, django_assert_max_num_queries
    ):
        with django_assert_max_num_queries(16):
            assert (
                operador.get(
                    reverse("viagens:editor_estado", args=[rascunho.pk, "oficio"])
                ).status_code
                == 200
            )
