"""Roteiros cadastrados (paridade com o sistema de referência) e o uso como modelo no ofício."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.viagens import services
from gestao.viagens.models import Oficio, Roteiro

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def operador(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    return client


def _data_hora(dias: int, hora: int) -> tuple[str, str]:
    alvo = timezone.localtime() + timedelta(days=dias)
    return alvo.strftime("%d/%m/%Y"), f"{hora:02d}:00"


def _post_roteiro(cidade="Ponta Grossa/PR", **extra) -> dict:
    uf = cidade.split("/")[1]
    dados = {
        "sede-uf": "PR", "sede-cidade": "Curitiba/PR",
        "destino-TOTAL_FORMS": "1", "destino-INITIAL_FORMS": "0",
        "destino-MIN_NUM_FORMS": "1", "destino-MAX_NUM_FORMS": "10",
        "destino-0-uf": uf, "destino-0-cidade": cidade, "destino-0-ORDER": "1",
        "destino-0-tempo_viagem": "02:00", "destino-0-tempo_adicional": "00:00",
        "retorno-tempo_viagem": "02:00", "retorno-tempo_adicional": "00:00",
    }
    for nome, (dias, hora) in {"destino-0-saida": (30, 8), "retorno-saida": (31, 15)}.items():
        dados[f"{nome}_0"], dados[f"{nome}_1"] = _data_hora(dias, hora)
    dados.update(extra)
    return dados


def _trechos(cenario, cidade=("Ponta Grossa", "PR"), dias=20):
    curitiba = Municipio.objects.get(nome="Curitiba", uf="PR")
    destino = Municipio.objects.get(nome=cidade[0], uf=cidade[1])
    saida = timezone.localtime().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(
        days=dias)
    return [
        services.TrechoInformado(curitiba.pk, destino.pk, saida, saida + timedelta(hours=2)),
        services.TrechoInformado(destino.pk, curitiba.pk, saida + timedelta(days=1, hours=7),
                                 saida + timedelta(days=1, hours=9)),
    ]


class TestServicosDoRoteiro:
    def test_diarias_sao_estimadas_para_o_efetivo_do_roteiro(self, cenario):
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro"])
        assert roteiro.diarias_resumo == "2 x 100% + 1 x 15%"
        assert roteiro.diarias_calculo["servidores"] == 3
        por_servidor = roteiro.diarias_total / 3
        roteiro = services.salvar_roteiro(cenario.usuarios["operador"], roteiro,
                                          {"quantidade_servidores": 1}, None)
        assert roteiro.diarias_total == por_servidor  # mudar o efetivo recalcula

    def test_sequencia_impossivel_nao_grava_nada(self, cenario):
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro"])
        ida, volta = _trechos(cenario)
        volta_antes = services.TrechoInformado(volta.origem_id, volta.destino_id,
                                               ida.chegada_em - timedelta(hours=1),
                                               ida.chegada_em + timedelta(hours=1))
        with pytest.raises(services.RegraViolada, match="sai antes da chegada"):
            services.salvar_roteiro(cenario.usuarios["operador"], roteiro, {}, [ida, volta_antes])
        assert roteiro.trechos.count() == 2

    def test_roteiro_sem_trechos_e_permitido_e_diz_o_que_falta(self, cenario):
        roteiro = services.salvar_roteiro(cenario.usuarios["operador"], None,
                                          {"quantidade_servidores": 2}, [])
        assert roteiro.trechos.count() == 0 and "Informe os trechos" in roteiro.diarias_erro

    def test_consulta_nao_cria_e_cancelado_nao_edita(self, cenario):
        with pytest.raises(PermissionDenied):
            services.salvar_roteiro(cenario.usuarios["consulta"], None, {}, [])
        cancelado = Roteiro.objects.get(pk=cenario.ids["roteiro_cancelado"])
        with pytest.raises(PermissionDenied):
            services.salvar_roteiro(cenario.usuarios["operador"], cancelado, {}, None)

    def test_criar_oficio_do_roteiro_copia_os_trechos_e_guarda_o_vinculo(self, cenario):
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro"])
        oficio = services.criar_oficio_do_roteiro(cenario.usuarios["operador"], roteiro)
        trechos = list(oficio.trechos.order_by("ordem"))
        originais = list(roteiro.trechos.order_by("ordem"))
        assert [(t.origem_id, t.destino_id, t.saida_em) for t in trechos] == [
            (t.origem_id, t.destino_id, t.saida_em) for t in originais]
        assert oficio.roteiro_id == roteiro.pk
        assert oficio.historico.filter(descricao__contains=f"roteiro #{roteiro.pk}").exists()
        # Copiar não amarra: mudar o roteiro depois não muda o ofício.
        services.salvar_roteiro(cenario.usuarios["operador"], roteiro, {}, _trechos(cenario,
                                                                                    dias=50))
        assert oficio.trechos.first().saida_em == trechos[0].saida_em

    def test_roteiro_de_outra_sede_leva_a_sede_para_o_oficio(self, cenario):
        """A sede é editável no itinerário 2.0: o ofício nasce saindo de onde o roteiro sai."""
        londrina = Municipio.objects.get(nome="Londrina", uf="PR")
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro"])
        Roteiro.objects.filter(pk=roteiro.pk).update(sede=londrina)
        roteiro.refresh_from_db()
        oficio = services.criar_oficio_do_roteiro(cenario.usuarios["operador"], roteiro)
        assert oficio.sede_id == londrina.pk and oficio.roteiro_id == roteiro.pk

    def test_roteiro_cancelado_nao_cria_oficio_nem_gasta_numero(self, cenario):
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro_cancelado"])
        antes = Oficio.objects.count()
        with pytest.raises(services.RegraViolada, match="cancelado"):
            services.criar_oficio_do_roteiro(cenario.usuarios["operador"], roteiro)
        assert Oficio.objects.count() == antes

    def test_excluir_roteiro_usado_e_bloqueado(self, cenario):
        roteiro = Roteiro.objects.get(pk=cenario.ids["roteiro"])
        services.criar_oficio_do_roteiro(cenario.usuarios["operador"], roteiro)
        with pytest.raises(services.RegraViolada, match="Cancele o roteiro"):
            services.excluir_roteiro(cenario.usuarios["operador"], roteiro)
        livre = Roteiro.objects.get(pk=cenario.ids["roteiro_cancelado"])
        services.excluir_roteiro(cenario.usuarios["operador"], livre)
        assert not Roteiro.objects.filter(pk=livre.pk).exists()


class TestTelasDeRoteiros:
    def test_lista_com_abas_contagens_e_busca(self, operador, cenario):
        r = operador.get(reverse("viagens:roteiros"))
        html = r.content.decode()
        assert r.status_code == 200
        # Marcador do registro, não "#id": "#12" também aparece no placeholder da busca.
        assert f'data-destaque="roteiro:{cenario.ids["roteiro"]}"' in html
        assert f'data-destaque="roteiro:{cenario.ids["roteiro_outra_unidade"]}"' not in html
        contagens = r.context["contagens"]
        assert contagens == {"todos": 2, "futuros": 1, "andamento": 0, "finalizados": 0,
                             "cancelados": 1}
        busca = operador.get(reverse("viagens:roteiros"), {"q": "ponta"}).context["roteiros"]
        assert [x.pk for x in busca] == [cenario.ids["roteiro"]]
        por_numero = operador.get(reverse("viagens:roteiros"),
                                  {"q": f"#{cenario.ids['roteiro_cancelado']}"})
        assert [x.pk for x in por_numero.context["roteiros"]] == [cenario.ids["roteiro_cancelado"]]
        cancelados = operador.get(reverse("viagens:roteiros"), {"aba": "cancelados"})
        assert [x.pk for x in cancelados.context["roteiros"]] == [cenario.ids["roteiro_cancelado"]]

    def test_lista_em_numero_fixo_de_consultas(self, operador, cenario,
                                               django_assert_max_num_queries):
        for _ in range(5):
            services.salvar_roteiro(cenario.usuarios["operador"], None,
                                    {"quantidade_servidores": 2}, _trechos(cenario))
        with django_assert_max_num_queries(18):  # +1 do sino, +1 da aba Finalizados
            assert operador.get(reverse("viagens:roteiros")).status_code == 200

    def test_outra_unidade_e_consulta(self, client, operador, cenario):
        outra = cenario.ids["roteiro_outra_unidade"]
        assert operador.get(reverse("viagens:editar_roteiro", args=[outra])).status_code == 403
        client.force_login(cenario.usuarios["consulta"])
        r = client.get(reverse("viagens:roteiros"))
        assert r.status_code == 200 and "Novo roteiro" not in r.content.decode()
        assert client.get(reverse("viagens:novo_roteiro")).status_code == 403

    def test_novo_roteiro_com_data_e_hora_separadas(self, operador):
        assert operador.get(reverse("viagens:novo_roteiro")).status_code == 200
        r = operador.post(reverse("viagens:novo_roteiro"), _post_roteiro())
        assert r.status_code == 302, r.content.decode()[:800]
        roteiro = Roteiro.objects.latest("pk")
        # Com autosave, "Salvar" quer dizer "terminei": volta para a lista.
        assert r["Location"] == reverse("viagens:roteiros")
        assert [t.destino.nome for t in roteiro.trechos.order_by("ordem")] == [
            "Ponta Grossa", "Curitiba"]
        # A tela não pede mais o efetivo: a estimativa do roteiro é para um servidor.
        assert roteiro.quantidade_servidores == 1 and roteiro.diarias_resumo

    def test_erro_volta_com_mensagem_e_nada_gravado(self, operador):
        antes = Roteiro.objects.count()
        r = operador.post(reverse("viagens:novo_roteiro"),
                          _post_roteiro(cidade="Cidade Inexistente/PR"))
        html = r.content.decode()
        assert r.status_code == 422 and Roteiro.objects.count() == antes
        assert "lista oficial de municípios" in html

    def test_adicionar_destino_preserva_o_digitado(self, operador, cenario):
        url = reverse("viagens:editar_roteiro", args=[cenario.ids["roteiro"]])
        html = operador.post(url, _post_roteiro(acao="adicionar_destino")).content.decode()
        assert 'name="destino-0-cidade" value="Ponta Grossa/PR"' in html
        assert 'name="destino-1-cidade"' in html and 'form="form-roteiro"' in html

    def test_cancelar_reativar_e_criar_oficio_por_post(self, operador, cenario):
        pk = cenario.ids["roteiro"]
        operador.post(reverse("viagens:cancelar_roteiro", args=[pk]))
        assert Roteiro.objects.get(pk=pk).situacao == "cancelado"
        operador.post(reverse("viagens:reativar_roteiro", args=[pk]))
        assert Roteiro.objects.get(pk=pk).situacao == "ativo"
        r = operador.post(reverse("viagens:criar_oficio_do_roteiro", args=[pk]))
        oficio = Oficio.objects.latest("pk")
        assert r["Location"] == reverse("viagens:editar", args=[oficio.pk])
        assert oficio.roteiro_id == pk and oficio.trechos.count() == 2


class TestOficioUsaRoteiro:
    def _dados_do_oficio(self, oficio, **extra):
        from .test_views import _post_edicao

        return _post_edicao(oficio, **extra)

    def test_escolha_lista_so_roteiros_ativos_da_unidade(self, operador, cenario):
        html = operador.get(reverse("viagens:editar", args=[cenario.ids["oficio_vazio"]]))
        html = html.content.decode()
        assert 'name="roteiro_modelo"' in html
        # Só o <select> dos roteiros: outros seletores da folha (viatura…) têm ids próprios.
        seletor = re.search(r'<select[^>]*name="roteiro_modelo".*?</select>', html, re.S)
        assert seletor is not None
        opcoes = seletor.group(0)
        assert f'<option value="{cenario.ids["roteiro"]}"' in opcoes
        assert f'<option value="{cenario.ids["roteiro_cancelado"]}"' not in opcoes
        assert f'<option value="{cenario.ids["roteiro_outra_unidade"]}"' not in opcoes

    def test_usar_roteiro_preenche_sem_gravar_e_preserva_o_digitado(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = self._dados_do_oficio(oficio, acao="usar_roteiro",
                                      roteiro_modelo=cenario.ids["roteiro"],
                                      motivo="Texto que a pessoa digitou")
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        html = r.content.decode()
        assert r.status_code == 200
        assert 'name="destino-0-cidade" value="Ponta Grossa/PR"' in html
        assert "Texto que a pessoa digitou" in html
        assert f'name="roteiro" value="{cenario.ids["roteiro"]}"' in html
        assert oficio.trechos.count() == 0  # nada gravado ainda

    def test_usar_roteiro_ja_mostra_a_previa_das_diarias(self, operador, cenario):
        """Com os trechos do roteiro na tela, a conta aparece antes de salvar.

        Regressão: o bloco de diárias olhava primeiro o `diarias_erro` gravado no ofício
        (ainda sem trechos) e dizia "Informe os trechos" com os trechos preenchidos logo
        acima, ignorando a prévia que a view tinha calculado.
        """
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = self._dados_do_oficio(oficio, acao="usar_roteiro",
                                      roteiro_modelo=cenario.ids["roteiro"])
        html = operador.post(reverse("viagens:editar", args=[oficio.pk]),
                             dados).content.decode()
        assert "Ainda não dá para calcular" not in html
        assert "Valor total" in html and "Quantidade por servidor" in html
        assert oficio.trechos.count() == 0  # a prévia não grava nada

    def test_salvar_depois_de_usar_grava_trechos_e_vinculo(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = self._dados_do_oficio(oficio, roteiro=cenario.ids["roteiro"])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 302, r.content.decode()[:600]
        oficio.refresh_from_db()
        assert oficio.roteiro_id == cenario.ids["roteiro"] and oficio.trechos.count() == 2
        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        assert f"roteiro #{cenario.ids['roteiro']}</a>" in html

    @pytest.mark.parametrize("chave", ["roteiro_cancelado", "roteiro_outra_unidade"])
    def test_roteiro_cancelado_ou_de_outra_unidade_nao_serve(self, operador, cenario, chave):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = self._dados_do_oficio(oficio, acao="usar_roteiro",
                                      roteiro_modelo=cenario.ids[chave])
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 422
        assert 'id="alerta-roteiro"' in r.content.decode()
