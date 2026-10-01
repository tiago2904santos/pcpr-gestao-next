"""Integração HTTP das telas do piloto (cliente de teste do Django + PostgreSQL)."""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise

import pytest
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor
from gestao.plataforma import outbox
from gestao.viagens import services
from gestao.viagens.models import Documento, Oficio

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
def gestor(client, cenario):
    client.force_login(cenario.usuarios["gestor"])
    return client


def _local(dias: int, hora: int, minuto: int = 0) -> str:
    alvo = timezone.localtime() + timedelta(days=dias)
    return alvo.replace(hour=hora, minute=minuto).strftime("%Y-%m-%dT%H:%M")


def _post_edicao(oficio: Oficio, **extra) -> dict:
    dados = {
        "versao": oficio.versao, "data_oficio": oficio.data_oficio.isoformat(),
        "protocolo": "12.345.678-9", "marcador": "", "motivo": "Pauta institucional",
        "custeio": "unidade", "tipo_transporte": "outro", "transporte_descricao": "Ônibus",
        "porte_arma": "on", "destino-TOTAL_FORMS": "1", "destino-INITIAL_FORMS": "0",
        "destino-MIN_NUM_FORMS": "1", "destino-MAX_NUM_FORMS": "10",
        "destino-0-cidade": "Ponta Grossa/PR", "destino-0-saida": _local(20, 8),
        "destino-0-chegada": _local(20, 10), "retorno-saida": _local(21, 15),
        "retorno-chegada": _local(21, 17),
    }
    dados.update(extra)
    return dados


class TestListaEPainel:
    def test_painel_inicio_e_modulo(self, operador):
        assert operador.get(reverse("painel:inicio")).status_code == 200
        r = operador.get(reverse("viagens:painel"))
        assert r.status_code == 200 and "Para concluir" in r.content.decode()

    @pytest.mark.parametrize("filtro", ["", "rascunho", "emitido", "proximos", "cancelado"])
    def test_abas_de_situacao(self, operador, filtro):
        r = operador.get(reverse("viagens:oficios"), {"situacao": filtro})
        assert r.status_code == 200

    def test_busca_e_parcial_htmx(self, operador, cenario):
        r = operador.get(reverse("viagens:oficios"), {"q": "arapongas"},
                         HTTP_HX_REQUEST="true", HTTP_HX_TARGET="resultados")
        html = r.content.decode()
        assert r.status_code == 200 and "<html" not in html and "Arapongas" in html

    @pytest.mark.parametrize("ordem", ["numero", "-numero", "saida", "-saida", "invalida"])
    def test_ordenacao(self, operador, ordem):
        assert operador.get(reverse("viagens:oficios"), {"ordem": ordem}).status_code == 200

    def test_sem_resultado_mostra_estado_vazio(self, operador):
        r = operador.get(reverse("viagens:oficios"), {"q": "zzz-inexistente"})
        assert "Nenhum ofício encontrado" in r.content.decode()

    def test_lista_tem_orcamento_de_consultas(self, operador, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            operador.get(reverse("viagens:oficios"))

    def test_busca_global_json(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        r = operador.get(reverse("painel:busca"), {"q": f"{oficio.numero}/{oficio.ano}"})
        assert r.json()["resultados"][0]["titulo"] == f"Ofício {oficio.numero_formatado}"
        assert operador.get(reverse("painel:busca"), {"q": "x"}).json() == {"resultados": []}


class TestNovoEEdicao:
    def test_novo_cria_rascunho_e_redireciona_para_equipe(self, operador):
        assert operador.get(reverse("viagens:novo")).status_code == 200
        r = operador.post(reverse("viagens:novo"), {"data_oficio": timezone.localdate(),
                                                    "motivo": "Teste"})
        assert r.status_code == 302 and r["Location"].endswith("#equipe")

    def test_novo_proibido_para_consulta(self, client, cenario):
        client.force_login(cenario.usuarios["consulta"])
        assert client.get(reverse("viagens:novo")).status_code == 403

    def test_editar_salva_dados_e_roteiro(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        assert operador.get(reverse("viagens:editar", args=[oficio.pk])).status_code == 200
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), _post_edicao(oficio))
        assert r.status_code == 302, r.content.decode()[:500]
        oficio.refresh_from_db()
        assert oficio.protocolo == "123456789"
        assert [t.destino.nome for t in oficio.trechos.order_by("ordem")] == [
            "Ponta Grossa", "Curitiba"]

    def test_revisar_e_emitir_com_pendencias_volta_para_a_secao(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, acao="emitir"), follow=True)
        assert r.redirect_chain[-1][0] == reverse("viagens:editar", args=[oficio.pk]) + "#emissao"
        assert "pendência" in r.content.decode()

    def test_revisar_e_emitir_pronto_vai_para_revisao(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        services.adicionar_viajante(oficio, cenario.usuarios["operador"],
                                    Servidor.objects.filter(ativo=True).first())
        oficio.refresh_from_db()
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, acao="emitir"))
        assert r["Location"] == reverse("viagens:revisar_emissao", args=[oficio.pk])

    def test_adicionar_destino_reexibe_sem_salvar(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, acao="adicionar_destino"))
        assert r.status_code == 200 and 'name="destino-1-cidade"' in r.content.decode()
        assert not oficio.trechos.exists()

    def test_erros_de_validacao_respondem_422(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, protocolo="123",
                                       **{"destino-0-cidade": "Atlantida/XX"}))
        html = r.content.decode()
        assert r.status_code == 422
        assert "O protocolo tem 9 dígitos" in html and "lista oficial de municípios" in html

    def test_regra_de_negocio_respondida_na_tela(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **{"destino-0-chegada": _local(22, 10)})
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 422 and "sai antes da chegada" in r.content.decode()
        # Dados e roteiro são uma gravação só: roteiro recusado não deixa dados pela metade.
        oficio.refresh_from_db()
        assert oficio.protocolo == "" and not oficio.trechos.exists()
        assert not oficio.historico.filter(acao="alterado").exists()

    def test_conflito_de_versao(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, versao=oficio.versao - 1 or 999))
        assert r.status_code == 422 and "Outra pessoa salvou" in r.content.decode()

    def test_emitido_redireciona_para_detalhe(self, operador, cenario):
        r = operador.get(reverse("viagens:editar", args=[cenario.ids["oficio_emitido"]]))
        assert r.status_code == 302 and "/editar/" not in r["Location"]

    def test_outra_unidade_e_404(self, operador, cenario):
        r = operador.get(reverse("viagens:detalhe", args=[cenario.ids["oficio_outra_unidade"]]))
        assert r.status_code == 404


class TestEquipe:
    def test_adicionar_motorista_remover_htmx(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        from gestao.cadastros.models import Servidor

        servidor = Servidor.objects.get(nome__startswith="João Pedro")
        url = reverse("viagens:adicionar_viajante", args=[oficio.pk])
        r = operador.post(url, {"id": servidor.pk}, HTTP_HX_REQUEST="true")
        assert r.status_code == 200 and r["HX-Trigger"] == "equipe-alterada"
        assert 'hx-swap-oob="true"' in r.content.decode()
        viajante = oficio.viajantes.get()
        operador.post(reverse("viagens:definir_motorista", args=[oficio.pk]),
                      {"viajante": viajante.pk}, HTTP_HX_REQUEST="true")
        viajante.refresh_from_db()
        assert viajante.motorista
        repetido = operador.post(url, {"id": servidor.pk}, HTTP_HX_REQUEST="true")
        assert "já está na equipe" in repetido.content.decode()
        r = operador.post(reverse("viagens:remover_viajante", args=[oficio.pk, viajante.pk]))
        assert r.status_code == 302 and not oficio.viajantes.exists()

    def test_api_de_servidores(self, operador):
        r = operador.get(reverse("viagens:buscar_servidores"), {"q": "isab"})
        assert r.json()["resultados"][0]["titulo"] == "Isabela Prado Cavalcanti"
        cpf = operador.get(reverse("viagens:buscar_servidores"), {"q": "123.456.700"})
        assert cpf.json()["resultados"]

    def test_api_de_municipios_prioriza_parana(self, operador):
        r = operador.get(reverse("cadastros:buscar_municipios"), {"q": "sao jose"})
        nomes = [x["titulo"] for x in r.json()["resultados"]]
        assert nomes[0].endswith("/PR")
        filtrado = operador.get(reverse("cadastros:buscar_municipios"), {"q": "curitiba/pr"})
        assert [x["titulo"] for x in filtrado.json()["resultados"]] == ["Curitiba/PR"]

    def test_secao_diarias(self, operador, cenario):
        r = operador.get(reverse("viagens:secao_diarias", args=[cenario.ids["oficio_emitido"]]))
        assert "4 x 100% + 1 x 15%" in r.content.decode()


class TestEmissaoEAcoes:
    def test_revisar_emitir_e_baixar(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        operador.post(reverse("viagens:editar", args=[oficio.pk]), _post_edicao(oficio))
        from gestao.cadastros.models import Servidor

        operador.post(reverse("viagens:adicionar_viajante", args=[oficio.pk]),
                      {"id": Servidor.objects.first().pk})
        assert operador.get(reverse("viagens:revisar_emissao", args=[oficio.pk])).status_code \
            == 200
        oficio.refresh_from_db()
        r = operador.post(reverse("viagens:emitir", args=[oficio.pk]), {"versao": oficio.versao})
        assert r["Location"] == reverse("viagens:detalhe", args=[oficio.pk])
        doc = oficio.documentos.get(tipo="oficio")
        assert operador.get(reverse("viagens:baixar_documento", args=[doc.pk])).status_code == 404
        while outbox.processar_lote():
            pass
        r = operador.get(reverse("viagens:baixar_documento", args=[doc.pk]), {"baixar": "1"})
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert "attachment" in r["Content-Disposition"]
        assert b"".join(r.streaming_content).startswith(b"%PDF")
        parcial = operador.get(reverse("viagens:documentos", args=[oficio.pk]))
        assert "PDF/A pronto" in parcial.content.decode()

    def test_emitir_com_pendencia_volta_com_mensagem(self, operador, cenario):
        pk = cenario.ids["oficio_rascunho"]
        r = operador.post(reverse("viagens:emitir", args=[pk]), follow=True)
        assert "Ainda há pendências" in r.content.decode()

    def test_minuta_pdf(self, operador, cenario):
        r = operador.get(reverse("viagens:previa", args=[cenario.ids["oficio_rascunho"]]))
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert operador.get(reverse("viagens:previa", args=[cenario.ids["oficio_rascunho"]]),
                            {"tipo": "x"}).status_code == 404

    def test_gestor_reabre_e_cancela(self, gestor, cenario):
        pk = cenario.ids["oficio_emitido"]
        assert gestor.post(reverse("viagens:reabrir", args=[pk]), {"motivo": ""},
                           follow=True).status_code == 200
        r = gestor.post(reverse("viagens:reabrir", args=[pk]), {"motivo": "Corrigir data"})
        assert r["Location"] == reverse("viagens:editar", args=[pk])
        r = gestor.post(reverse("viagens:cancelar", args=[pk]), {"motivo": ""}, follow=True)
        assert "Informe o motivo" in r.content.decode()
        gestor.post(reverse("viagens:cancelar", args=[pk]), {"motivo": "Evento cancelado"})
        assert Oficio.objects.get(pk=pk).situacao == "cancelado"
        detalhe = gestor.get(reverse("viagens:detalhe", args=[pk])).content.decode()
        assert "Ofício cancelado em" in detalhe and "Evento cancelado" in detalhe

    def test_operador_nao_cancela(self, operador, cenario):
        r = operador.post(reverse("viagens:cancelar", args=[cenario.ids["oficio_emitido"]]),
                          {"motivo": "x"})
        assert r.status_code == 403

    def test_excluir_rascunho(self, operador, cenario):
        pk = cenario.ids["oficio_vazio"]
        r = operador.post(reverse("viagens:excluir", args=[pk]))
        assert r.status_code == 302 and not Oficio.objects.filter(pk=pk).exists()

    def test_detalhe_mostra_historico_e_documentos(self, operador, cenario):
        r = operador.get(reverse("viagens:detalhe", args=[cenario.ids["oficio_emitido"]]))
        html = r.content.decode()
        assert "Histórico" in html and "emitido" in html and "Gerando" in html
        assert Documento.objects.filter(oficio_id=cenario.ids["oficio_emitido"]).exists()


class TestCadastrosEPlataforma:
    @pytest.mark.parametrize("rota", ["cadastros:servidores", "cadastros:viaturas",
                                      "cadastros:diarias"])
    def test_consultas_de_cadastro(self, operador, rota):
        assert operador.get(reverse(rota)).status_code == 200

    def test_busca_de_servidores_no_cadastro(self, operador):
        r = operador.get(reverse("cadastros:servidores"), {"q": "Bruno"})
        assert "Bruno Henrique Martins" in r.content.decode()

    def test_tabela_de_diarias_mostra_percentuais_calculados(self, operador):
        html = operador.get(reverse("cadastros:diarias")).content.decode()
        assert "R$ 43,58" in html and "R$ 87,17" in html and "R$ 140,44" in html

    def test_paginas_de_erro_e_saude(self, operador, client):
        r = operador.get("/rota-que-nao-existe/")
        assert r.status_code == 404 and "Página não encontrada" in r.content.decode()
        assert operador.get(reverse("painel:notificacoes")).status_code == 200
        assert operador.get(reverse("ui_lab:indice")).status_code == 200
        assert operador.get(reverse("ui_lab:busca_exemplo"), {"q": "bru"}).json()["resultados"]
        client.logout()
        assert client.get(reverse("saude")).json() == {"status": "ok", "banco": "ok"}

    def test_cabecalho_mostra_papel(self, operador):
        html = operador.get(reverse("painel:inicio")).content.decode()
        assert "Operador de viagens" in html


class TestRoteiroComVoltaIntermediaria:
    """R3 (paridade): bate-volta com passagem pela sede não pode perder trechos ao reabrir."""

    def test_reabrir_e_salvar_preserva_volta_intermediaria(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **{
            "destino-TOTAL_FORMS": "3",
            "destino-0-cidade": "Ponta Grossa/PR", "destino-0-saida": _local(20, 8),
            "destino-0-chegada": _local(20, 10),
            "destino-1-cidade": "Curitiba/PR", "destino-1-saida": _local(20, 16),
            "destino-1-chegada": _local(20, 18),
            "destino-2-cidade": "Paranaguá/PR", "destino-2-saida": _local(21, 8),
            "destino-2-chegada": _local(21, 10),
            "retorno-saida": _local(21, 15), "retorno-chegada": _local(21, 17),
        })
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 302, r.content.decode()[:300]
        oficio.refresh_from_db()
        antes = (list(oficio.trechos.values_list("destino__nome", flat=True).order_by("ordem")),
                 oficio.diarias_total)
        assert antes[0] == ["Ponta Grossa", "Curitiba", "Paranaguá", "Curitiba"]

        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        assert 'name="destino-2-cidade"' in html and 'value="Curitiba/PR"' in html
        # Reenvia o formulário exatamente como reaberto: nada pode mudar.
        from gestao.viagens.forms import iniciais_do_roteiro

        destinos, retorno = iniciais_do_roteiro(oficio)
        reenvio = _post_edicao(oficio, versao=oficio.versao,
                               **{"destino-TOTAL_FORMS": str(len(destinos)),
                                  "retorno-saida": retorno["saida"],
                                  "retorno-chegada": retorno["chegada"]})
        for i, d in enumerate(destinos):
            for campo in ("cidade", "saida", "chegada"):
                reenvio[f"destino-{i}-{campo}"] = d[campo]
        assert operador.post(reverse("viagens:editar", args=[oficio.pk]), reenvio).status_code \
            == 302
        oficio.refresh_from_db()
        depois = (list(oficio.trechos.values_list("destino__nome", flat=True).order_by("ordem")),
                  oficio.diarias_total)
        assert depois == antes


class TestOrcamentoDeConsultas:
    """Telas do ofício em número fixo de consultas, independente do tamanho da equipe/roteiro."""

    @staticmethod
    def _engordar(oficio: Oficio, usuario) -> None:
        for servidor in Servidor.objects.filter(ativo=True).exclude(
                pk__in=oficio.viajantes.values("servidor"))[:4]:
            services.adicionar_viajante(oficio, usuario, servidor)
        sede, agora = oficio.sede, timezone.now()
        cidades = list(Municipio.objects.filter(uf="PR").exclude(pk=sede.pk)[:3])
        paradas = [sede, *cidades, sede]
        services.salvar_trechos(oficio, usuario, [
            services.TrechoInformado(a.pk, b.pk, agora + timedelta(days=20, hours=10 * i),
                                     agora + timedelta(days=20, hours=10 * i + 3))
            for i, (a, b) in enumerate(pairwise(paradas))
        ])

    @pytest.mark.parametrize("engordar", [False, True], ids=["pequeno", "grande"])
    @pytest.mark.parametrize("rota", ["viagens:editar", "viagens:revisar_emissao",
                                      "viagens:detalhe"])
    def test_paginas_do_oficio(self, operador, cenario, django_assert_max_num_queries,
                               rota, engordar):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
        if engordar:
            self._engordar(oficio, cenario.usuarios["operador"])
        with django_assert_max_num_queries(20):
            assert operador.get(reverse(rota, args=[oficio.pk])).status_code == 200

    def test_salvar_edicao(self, operador, cenario, django_assert_max_num_queries):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
        with django_assert_max_num_queries(25):
            r = operador.post(reverse("viagens:editar", args=[oficio.pk]), _post_edicao(oficio))
        assert r.status_code == 302


class TestProvasDaRevisaoDeUX:
    """Cada correção da revisão de UX/paridade com um teste que reprova sem ela."""

    def test_documento_retroativo_sai_como_convalidacao(self, cenario):
        from gestao.viagens.documentos.dados import dados_do_oficio
        from gestao.viagens.documentos.pdf import html_do_documento

        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        sede = oficio.sede
        destino = Municipio.objects.filter(uf="PR").exclude(pk=sede.pk).first()
        ontem = timezone.now() - timedelta(days=3)
        services.salvar_trechos(oficio, cenario.usuarios["operador"], [
            services.TrechoInformado(sede.pk, destino.pk, ontem, ontem + timedelta(hours=3)),
            services.TrechoInformado(destino.pk, sede.pk, ontem + timedelta(days=1),
                                     ontem + timedelta(days=1, hours=3)),
        ])
        oficio.refresh_from_db()
        dados = dados_do_oficio(oficio)
        assert dados["assunto_termo"] == "convalidação"
        html = html_do_documento("oficio", dados)
        assert "solicito convalidação" in html and "(Convalidação)" in html
        assert "(Autorização)" not in html

    def test_busca_ao_vivo_atualiza_abas_preservando_busca_e_ordem(self, operador):
        r = operador.get(reverse("viagens:oficios"), {"q": "arapongas", "ordem": "saida"},
                         HTTP_HX_REQUEST="true", HTTP_HX_TARGET="resultados")
        html = r.content.decode()
        assert 'id="abas-filtro"' in html and 'hx-swap-oob="true"' in html
        assert "?situacao=rascunho&q=arapongas&ordem=saida" in html

    def test_adicionar_destino_e_erro_marcam_alteracoes_nao_salvas(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        url = reverse("viagens:editar", args=[oficio.pk])
        assert "data-sujo" not in operador.get(url).content.decode()
        for extra in ({"acao": "adicionar_destino"}, {"protocolo": "123"}):
            html = operador.post(url, _post_edicao(oficio, **extra)).content.decode()
            assert "data-sujo" in html and "Alterações não salvas" in html

    def test_consulta_nao_ve_continuar_edicao_e_recebe_mensagem_certa(self, client, cenario):
        client.force_login(cenario.usuarios["consulta"])
        lista = client.get(reverse("viagens:oficios")).content.decode()
        assert "Continuar edição" not in lista and "Ver detalhes" in lista
        r = client.get(reverse("viagens:editar", args=[cenario.ids["oficio_rascunho"]]),
                       follow=True)
        assert "Seu perfil permite consultar, mas não editar ofícios." in r.content.decode()
