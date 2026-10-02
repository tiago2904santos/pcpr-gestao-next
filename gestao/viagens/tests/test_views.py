"""Integração HTTP das telas do piloto (cliente de teste do Django + PostgreSQL)."""

from __future__ import annotations

import re
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


def _itinerario(*destinos: tuple[str, str], volta: str, sede: str = "Curitiba/PR",
                viagem: str = "02:00", adicional: str = "00:00") -> dict:
    """Campos do itinerário 2.0: sede, destinos (cidade, saída) na ordem e a volta. Só a
    saída é informada; a chegada = saída + tempo de viagem + tempo adicional."""
    dados = {"sede-uf": sede.split("/")[1], "sede-cidade": sede,
             "destino-TOTAL_FORMS": str(len(destinos)), "destino-INITIAL_FORMS": "0",
             "destino-MIN_NUM_FORMS": "1", "destino-MAX_NUM_FORMS": "10",
             "retorno-saida": volta, "retorno-tempo_viagem": viagem,
             "retorno-tempo_adicional": adicional}
    for i, (cidade, saida) in enumerate(destinos):
        dados.update({f"destino-{i}-uf": cidade.split("/")[1], f"destino-{i}-cidade": cidade,
                      f"destino-{i}-saida": saida, f"destino-{i}-ORDER": str(i + 1),
                      f"destino-{i}-tempo_viagem": viagem,
                      f"destino-{i}-tempo_adicional": adicional})
    return dados


def _post_edicao(oficio: Oficio, **extra) -> dict:
    dados = {
        "versao": oficio.versao, "data_oficio": oficio.data_oficio.isoformat(),
        "protocolo": "12.345.678-9", "marcador": "", "motivo": "Pauta institucional",
        "custeio": "unidade", "tipo_transporte": "outro", "transporte_descricao": "Ônibus",
        "porte_arma": "on", **_itinerario(("Ponta Grossa/PR", _local(20, 8)),
                                          volta=_local(21, 15)),
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

    def test_busca_oferece_as_leituras_do_termo_com_contagem(self, operador, cenario):
        """"26" pode ser o número do ofício ou pedaço de protocolo: a tela pergunta em vez
        de misturar os dois no mesmo resultado."""
        usuario = cenario.usuarios["operador"]
        for _ in range(9):
            services.criar_rascunho(usuario)
        alvo = services.criar_rascunho(usuario)  # número de dois dígitos
        termo = str(alvo.numero)
        services.salvar_dados(alvo, usuario, {"protocolo": f"{termo}0000000"[:9]})
        html = operador.get(reverse("viagens:oficios"), {"q": termo}).content.decode()
        assert f"Ofício {alvo.numero}/{alvo.ano}" in html and "escopo=numero" in html
        assert "Protocolo com" in html and "escopo=protocolo" in html

    def test_busca_com_escopo_procura_so_onde_foi_pedido(self, operador, cenario):
        """Com escopo de protocolo, o número do ofício não entra no resultado."""
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])  # protocolo 123456789
        html = operador.get(reverse("viagens:oficios"),
                            {"q": "456", "escopo": "protocolo"}).content.decode()
        assert oficio.numero_formatado in html and "Buscando em" in html

    def test_escopo_inexistente_cai_na_busca_ampla(self, operador, cenario):
        r = operador.get(reverse("viagens:oficios"), {"q": "arapongas", "escopo": "placa"})
        assert r.status_code == 200 and "Arapongas" in r.content.decode()

    def test_filtro_avancado_por_periodo_de_saida(self, operador, cenario):
        """A faixa vale pela ida: só entra quem sai dentro dela."""
        hoje = timezone.localdate()
        html = operador.get(reverse("viagens:oficios"), {
            "saida_de": (hoje + timedelta(days=10)).strftime("%d/%m/%Y"),
            "saida_ate": (hoje + timedelta(days=25)).strftime("%d/%m/%Y"),
        }).content.decode()
        assert "Arapongas" in html  # sai em hoje+20
        assert "Maringá" not in html and "São Paulo" not in html  # hoje+3 e hoje+30

    def test_filtro_avancado_por_protocolo(self, operador, cenario):
        """O protocolo é comparado só pelos dígitos: a pontuação é da tela."""
        html = operador.get(reverse("viagens:oficios"),
                            {"protocolo": "12.345"}).content.decode()
        assert "1 ofício" in html and "Arapongas" in html

    def test_filtro_avancado_por_veiculo_sem_transporte(self, operador, cenario):
        html = operador.get(reverse("viagens:oficios"), {"veiculo": "sem"}).content.decode()
        assert "1 ofício" in html and "Sem transporte" in html

    def test_filtro_avancado_por_veiculo_pela_descricao(self, operador, cenario):
        """Ônibus, caminhão e unidade móvel não são campo no cadastro: valem pelo que está
        escrito no modelo da viatura ou na descrição do transporte."""
        html = operador.get(reverse("viagens:oficios"), {"veiculo": "onibus"}).content.decode()
        assert "1 ofício" in html and "Ônibus de linha" in html

    def test_filtro_avancado_por_valor_de_diarias(self, operador, cenario):
        emitido = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        acima = int(emitido.diarias_total) + 1
        html = operador.get(reverse("viagens:oficios"),
                            {"diarias_de": str(acima)}).content.decode()
        assert emitido.numero_formatado not in html

    def test_filtro_rabiscado_nao_derruba_a_lista(self, operador, cenario):
        """Data inválida ou opção inventada não viram erro: a lista continua respondendo."""
        r = operador.get(reverse("viagens:oficios"),
                         {"saida_de": "32/13/abcd", "veiculo": "inexistente"})
        assert r.status_code == 200 and "Arapongas" in r.content.decode()

    def test_abas_preservam_os_filtros_avancados(self, operador, cenario):
        html = operador.get(reverse("viagens:oficios"),
                            {"protocolo": "12345"}).content.decode()
        assert "situacao=emitido&amp;protocolo=12345" in html

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
    def test_novo_cria_o_oficio_e_abre_a_edicao(self, operador):
        """Como no sistema de referência: o botão já cria o ofício (número reservado) e abre a
        folha completa. Não há página intermediária."""
        antes = Oficio.objects.count()
        r = operador.post(reverse("viagens:novo"))
        oficio = Oficio.objects.latest("pk")
        assert Oficio.objects.count() == antes + 1
        assert oficio.situacao == Oficio.Situacao.RASCUNHO
        assert r["Location"] == reverse("viagens:editar", args=[oficio.pk])
        html = operador.get(r["Location"]).content.decode()
        assert f"Ofício {oficio.numero_formatado}" in html
        for secao in ('id="dados"', 'id="equipe"', 'id="roteiro"', 'id="emissao"'):
            assert secao in html

    def test_novo_por_get_nao_cria_nada(self, operador):
        antes = Oficio.objects.count()
        r = operador.get(reverse("viagens:novo"))
        assert r.status_code == 302 and r["Location"] == reverse("viagens:oficios")
        assert Oficio.objects.count() == antes

    def test_botao_novo_oficio_e_um_formulario_post(self, operador):
        url = reverse("viagens:novo")
        for pagina in ("viagens:oficios", "viagens:painel"):
            html = operador.get(reverse(pagina)).content.decode()
            assert f'method="post" action="{url}"' in html
            assert f'href="{url}"' not in html

    def test_aviso_de_conflito_nao_deixa_a_secao_pendente(self, operador, cenario):
        """Servidor em outro ofício no mesmo período é aviso: a seção Equipe segue pronta,
        coerente com a conferência ("tudo pronto para emitir")."""
        servidores = list(Servidor.objects.filter(ativo=True).order_by("pk")[:2])
        for _ in range(2):
            operador.post(reverse("viagens:novo"))
            oficio = Oficio.objects.latest("pk")
            for servidor in servidores:
                services.adicionar_viajante(oficio, cenario.usuarios["operador"], servidor)
            oficio.refresh_from_db()
            r = operador.post(reverse("viagens:editar", args=[oficio.pk]), _post_edicao(oficio))
            assert r.status_code == 302, r.content.decode()[:500]
        oficio = Oficio.objects.get(pk=oficio.pk)
        prontidao = services.verificar_prontidao(oficio)
        assert prontidao.da_secao("equipe") and prontidao.pode_emitir
        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        assert 'conferencia__item conferencia__item--ok">Equipe' in html

    def test_roteiro_com_data_e_hora_em_campos_separados(self, operador, cenario):
        """O calendário e o relógio enviam data (dd/mm/aaaa) e hora (hh:mm) em dois campos."""
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, data_oficio=timezone.localdate().strftime("%d/%m/%Y"))
        esperado = dados["destino-0-saida"]
        for nome in ("destino-0-saida", "retorno-saida"):
            data, hora = dados.pop(nome).split("T")
            ano, mes, dia = data.split("-")
            dados[f"{nome}_0"], dados[f"{nome}_1"] = f"{dia}/{mes}/{ano}", hora
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 302, r.content.decode()[:800]
        primeiro = oficio.trechos.order_by("ordem").first()
        assert timezone.localtime(primeiro.saida_em).strftime("%Y-%m-%dT%H:%M") == esperado

    def test_adicionar_destino_preserva_data_e_hora_separadas(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, acao="adicionar_destino")
        dados.pop("destino-0-saida")
        dados.update({"destino-0-saida_0": "08/10/2026", "destino-0-saida_1": "07:30",
                      "destino-0-tempo_viagem": "04:15", "destino-0-uf": "SC",
                      "destino-0-cidade": "Joinville/SC"})
        html = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados).content.decode()
        assert 'name="destino-0-saida_1" value="07:30"' in html
        assert 'name="destino-0-tempo_viagem" value="04:15"' in html
        # A nova parada começa na UF da sede (filtra os municípios), não na do destino anterior.
        assert 'name="destino-1-cidade"' in html
        assert re.search(r'<option value="PR" selected>[^<]*</option>', html.split(
            'name="destino-1-uf"')[1]) is not None

    def test_data_invalida_volta_com_mensagem_clara(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                          _post_edicao(oficio, data_oficio="31/02/2026"))
        assert r.status_code == 422
        assert "Informe a data no formato dd/mm/aaaa" in r.content.decode()

    def test_novo_proibido_para_consulta(self, client, cenario):
        client.force_login(cenario.usuarios["consulta"])
        antes = Oficio.objects.count()
        assert client.get(reverse("viagens:novo")).status_code == 403
        assert client.post(reverse("viagens:novo")).status_code == 403
        assert Oficio.objects.count() == antes

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
        # Chega a Ponta Grossa às 10h (8h + 2h de estrada), mas a volta sai às 9h.
        dados = _post_edicao(oficio, **{"retorno-saida": _local(20, 9)})
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

    def test_emitido_volta_para_a_lista(self, operador, cenario):
        """Emitido não tem folha para abrir: a leitura é a janela de resumo, na lista."""
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        r = operador.get(reverse("viagens:editar", args=[oficio.pk]))
        assert r.status_code == 302
        assert r["Location"] == f"{reverse('viagens:oficios')}?q={oficio.numero_formatado}"

    def test_outra_unidade_e_404(self, operador, cenario):
        r = operador.get(reverse("viagens:editar", args=[cenario.ids["oficio_outra_unidade"]]))
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
        assert r["Location"] == f"{reverse('viagens:oficios')}?q={oficio.numero_formatado}"
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
        resumo = gestor.get(reverse("viagens:resumo", args=[pk]),
                            HTTP_HX_REQUEST="true").content.decode()
        assert "Cancelado" in resumo

    def test_operador_nao_cancela(self, operador, cenario):
        r = operador.post(reverse("viagens:cancelar", args=[cenario.ids["oficio_emitido"]]),
                          {"motivo": "x"})
        assert r.status_code == 403

    def test_excluir_rascunho(self, operador, cenario):
        pk = cenario.ids["oficio_vazio"]
        r = operador.post(reverse("viagens:excluir", args=[pk]))
        assert r.status_code == 302 and not Oficio.objects.filter(pk=pk).exists()

    def test_resumo_do_registro_traz_roteiro_equipe_e_documentos(self, operador, cenario):
        """Clicar no registro abre uma janela com o resumo (fragmento HTMX)."""
        r = operador.get(reverse("viagens:resumo", args=[cenario.ids["oficio_emitido"]]),
                         HTTP_HX_REQUEST="true")
        html = r.content.decode()
        assert r.status_code == 200 and 'class="resumo"' in html
        assert "Roteiro" in html and "Equipe" in html and "Documentos" in html
        assert "<html" not in html  # fragmento, não página inteira

    @pytest.mark.parametrize("chave,limite", [("oficio_rascunho", 16), ("oficio_emitido", 14)])
    def test_resumo_tem_orcamento_de_consultas(self, operador, cenario, chave, limite,
                                               django_assert_max_num_queries):
        with django_assert_max_num_queries(limite):
            operador.get(reverse("viagens:resumo", args=[cenario.ids[chave]]),
                         HTTP_HX_REQUEST="true")

    def test_resumo_respeita_a_visibilidade_por_unidade(self, operador, cenario):
        r = operador.get(reverse("viagens:resumo", args=[cenario.ids["oficio_outra_unidade"]]))
        assert r.status_code == 404

    def test_salvar_confirma_na_barra_de_acoes_sem_toast(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), _post_edicao(oficio),
                          follow=True)
        html = r.content.decode()
        assert "?salvo=1" in r.redirect_chain[-1][0]
        assert "Rascunho salvo às" in html and "barra-acoes__status--salvo" in html
        assert "Rascunho do Ofício" not in html  # sem toast para o trivial

    def test_folha_mostra_historico_e_janela_mostra_documentos(self, operador, cenario):
        """O histórico ficou na folha de edição; os documentos, na janela de resumo."""
        rascunho = cenario.ids["oficio_rascunho"]
        folha = operador.get(reverse("viagens:editar", args=[rascunho])).content.decode()
        assert "Histórico" in folha and "criado" in folha
        emitido = cenario.ids["oficio_emitido"]
        janela = operador.get(reverse("viagens:resumo", args=[emitido]),
                              HTTP_HX_REQUEST="true").content.decode()
        assert "Documentos" in janela
        assert Documento.objects.filter(oficio_id=emitido).exists()


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
        dados = _post_edicao(oficio, **_itinerario(
            ("Ponta Grossa/PR", _local(20, 8)), ("Curitiba/PR", _local(20, 16)),
            ("Paranaguá/PR", _local(21, 8)), volta=_local(21, 15)))
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
                               **{"destino-TOTAL_FORMS": str(len(destinos))})
        for campo in ("saida", "tempo_viagem", "tempo_adicional"):
            reenvio[f"retorno-{campo}"] = retorno[campo]
        for i, d in enumerate(destinos):
            for campo in ("uf", "cidade", "saida", "tempo_viagem", "tempo_adicional", "ORDER"):
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
    @pytest.mark.parametrize("rota", ["viagens:editar", "viagens:revisar_emissao"])
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

    def test_lista_declara_vary_para_o_voltar_do_navegador_nao_mostrar_fragmento(
            self, operador):
        r = operador.get(reverse("viagens:oficios"), {"q": "x"}, HTTP_HX_REQUEST="true",
                         HTTP_HX_TARGET="resultados")
        assert {"HX-Request", "HX-Target"} <= {h.strip() for h in r["Vary"].split(",")}

    def test_busca_ao_vivo_atualiza_abas_preservando_busca_e_ordem(self, operador):
        r = operador.get(reverse("viagens:oficios"), {"q": "arapongas", "ordem": "saida"},
                         HTTP_HX_REQUEST="true", HTTP_HX_TARGET="resultados")
        html = r.content.decode()
        assert 'id="abas-filtro"' in html and 'hx-swap-oob="true"' in html
        assert "?situacao=rascunho&amp;q=arapongas&amp;ordem=saida" in html

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


class TestDecisoesDoDono:
    def test_bate_volta_sai_por_trechos_no_documento(self, cenario):
        """D7: voltas intermediárias aparecem como trechos numerados, na ordem."""
        from gestao.viagens.documentos.dados import dados_do_oficio
        from gestao.viagens.documentos.pdf import html_do_documento

        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        sede = oficio.sede
        destino = Municipio.objects.filter(uf="PR").exclude(pk=sede.pk).first()
        dia = timezone.now() + timedelta(days=20)
        hora = timedelta(hours=1)
        services.salvar_trechos(oficio, cenario.usuarios["operador"], [
            services.TrechoInformado(sede.pk, destino.pk, dia, dia + 2 * hora),
            services.TrechoInformado(destino.pk, sede.pk, dia + 8 * hora, dia + 10 * hora),
            services.TrechoInformado(sede.pk, destino.pk, dia + 24 * hora, dia + 26 * hora),
            services.TrechoInformado(destino.pk, sede.pk, dia + 32 * hora, dia + 34 * hora),
        ])
        oficio.refresh_from_db()
        dados = dados_do_oficio(oficio)
        assert dados["bate_volta"] and len(dados["trechos"]) == 4
        html = html_do_documento("oficio", dados)
        assert "ROTEIRO POR TRECHOS" in html and "Trecho 4" in html
        assert "ROTEIRO DE IDA" not in html

    def test_viagem_simples_continua_com_ida_e_retorno(self, cenario):
        from gestao.viagens.documentos.dados import dados_do_oficio
        from gestao.viagens.documentos.pdf import html_do_documento

        oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        html = html_do_documento("oficio", dados_do_oficio(oficio))
        assert "ROTEIRO DE IDA" in html and "ROTEIRO DE RETORNO" in html
        assert "ROTEIRO POR TRECHOS" not in html

    def test_numero_impresso_com_dois_digitos(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
        html = operador.get(reverse("viagens:resumo", args=[oficio.pk]),
                            HTTP_HX_REQUEST="true").content.decode()
        assert f"Ofício {oficio.numero:02d}/{oficio.ano}" in html
        assert f"{oficio.numero:03d}/{oficio.ano}" not in html
