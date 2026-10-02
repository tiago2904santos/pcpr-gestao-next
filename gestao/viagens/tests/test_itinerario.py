"""Itinerário 2.0 (ADR 0016): rotas, API do mapa, UF que filtra, ordem por arrastar, sede
editável e chegada calculada (saída + tempo de viagem + tempo adicional)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.viagens import rotas
from gestao.viagens.models import DistanciaMunicipios, Oficio

from .cenarios import cenario_completo
from .test_views import _itinerario, _local, _post_edicao

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    return cenario_completo()


@pytest.fixture
def operador(client, cenario):
    client.force_login(cenario.usuarios["operador"])
    return client


def _m(nome: str, uf: str = "PR") -> Municipio:
    return Municipio.objects.get(nome=nome, uf=uf)


class TestRotas:
    @pytest.mark.parametrize(("minutos", "esperado"), [(0, 0), (119, 0), (120, 15), (270, 30),
                                                       (480, 60)])
    def test_tempo_adicional_sugerido_15_min_a_cada_2h(self, minutos, esperado):
        assert rotas.tempo_adicional_sugerido(minutos) == esperado

    @pytest.mark.parametrize(("minutos", "esperado"), [(1, 15), (15, 15), (16, 30), (101.5, 105)])
    def test_tempo_de_viagem_arredonda_para_cima_em_15(self, minutos, esperado):
        assert rotas.arredondar_minutos(minutos) == esperado

    def test_estimativa_offline_usa_coordenadas_oficiais(self, cenario):
        perna = rotas.estimar(_m("Curitiba"), _m("Ponta Grossa"))
        # ~ 98 km em linha reta × 1,3 ≈ 128 km de estrada; a 70 km/h ≈ 1h50 → 2h00.
        assert Decimal(115) < perna.km < Decimal(140)
        assert perna.minutos == 120 and perna.fonte == "estimativa"
        assert len(perna.tracado) == 2

    def test_mesma_cidade_e_zero(self, cenario):
        perna = rotas.calcular(_m("Curitiba"), _m("Curitiba"))
        assert perna.km == 0 and perna.minutos == 0

    @override_settings(ROTAS_PROVEDOR="osrm", ROTAS_URL="https://rotas.invalido")
    def test_provedor_responde_e_fica_em_cache(self, cenario, monkeypatch):
        chamadas = []

        def falso(a, b):
            chamadas.append((a, b))
            return 117_400.0, 6_300.0, [[-49.27, -25.43], [-50.16, -25.09]]

        monkeypatch.setitem(rotas.PROVEDORES, "osrm", falso)
        perna = rotas.calcular(_m("Curitiba"), _m("Ponta Grossa"))
        assert perna.km == Decimal("117.4") and perna.minutos == 105 and perna.fonte == "osrm"
        assert perna.tracado[0] == [-25.43, -49.27]  # [lat, lon] para o mapa
        de_novo = rotas.calcular(_m("Curitiba"), _m("Ponta Grossa"))
        assert de_novo.km == perna.km and len(chamadas) == 1
        assert DistanciaMunicipios.objects.count() == 1

    @override_settings(ROTAS_PROVEDOR="osrm", ROTAS_URL="https://rotas.invalido")
    def test_provedor_fora_do_ar_cai_na_estimativa(self, cenario, monkeypatch):
        def quebrado(a, b):
            raise OSError("sem rede")

        monkeypatch.setitem(rotas.PROVEDORES, "osrm", quebrado)
        perna = rotas.calcular(_m("Curitiba"), _m("Ponta Grossa"))
        assert perna.fonte == "estimativa" and perna.minutos > 0
        assert not DistanciaMunicipios.objects.exists()  # estimativa não vira cache

    def test_url_sem_https_e_recusada(self):
        with pytest.raises(ValueError, match="inválida"):
            rotas._baixar_json("file:///etc/passwd")


class TestApiDaRota:
    def test_pernas_totais_e_pontos_com_coordenadas(self, operador):
        r = operador.get(reverse("viagens:rota"),
                         {"p": ["Curitiba/PR", "Ponta Grossa/PR", "Curitiba/PR"]})
        dados = r.json()
        assert r.status_code == 200 and len(dados["pernas"]) == 2
        assert all(p["lat"] and p["lon"] for p in dados["pontos"])
        ida, volta = dados["pernas"]
        assert ida["km"] == volta["km"] and ida["minutos"] == 120
        assert ida["adicional_sugerido"] == 15  # 2 h de estrada → uma pausa de 15 min
        assert dados["total"]["km"] == round(ida["km"] * 2, 1)

    def test_parada_invalida_volta_com_erro_sem_derrubar_o_resto(self, operador):
        dados = operador.get(reverse("viagens:rota"),
                             {"p": ["Curitiba/PR", "Atlantida/XX", "Curitiba/PR"]}).json()
        assert "erro" in dados["pontos"][1] and dados["pernas"] == [None, None]

    def test_sem_permissao_e_403(self, client):
        from django.contrib.auth import get_user_model

        sem_papel = get_user_model().objects.create_user("sem.papel", "sem.papel@pcpr.test", "x")
        client.force_login(sem_papel)
        assert client.get(reverse("viagens:rota"), {"p": "Curitiba/PR"}).status_code == 403


class TestFormularioDoItinerario:
    def test_chegada_e_calculada_saida_mais_viagem_mais_adicional(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(("Ponta Grossa/PR", _local(20, 8)),
                                                   volta=_local(21, 15), viagem="02:15",
                                                   adicional="00:30"))
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 302, r.content.decode()[:600]
        ida = oficio.trechos.order_by("ordem").first()
        assert ida.chegada_em - ida.saida_em == timedelta(hours=2, minutes=45)
        assert (ida.tempo_viagem_min, ida.tempo_adicional_min) == (135, 30)
        assert ida.distancia_km  # a rota (estimativa nos testes) grava a distância

    def test_tempos_em_branco_vem_da_rota_e_da_sugestao(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(("Londrina/PR", _local(20, 6)),
                                                   volta=_local(22, 15), viagem="",
                                                   adicional=""))
        assert operador.post(reverse("viagens:editar", args=[oficio.pk]),
                             dados).status_code == 302
        ida = oficio.trechos.order_by("ordem").first()
        esperado = rotas.estimar(_m("Curitiba"), _m("Londrina"))
        assert ida.tempo_viagem_min == esperado.minutos
        assert ida.tempo_adicional_min == esperado.adicional_sugerido > 0
        assert ida.chegada_em == ida.saida_em + timedelta(
            minutes=esperado.minutos + esperado.adicional_sugerido)

    def test_municipio_de_outra_uf_e_recusado(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **{"destino-0-uf": "SC"})
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 422
        assert "Escolha um município de SC (ou mude a UF)." in r.content.decode()
        assert not oficio.trechos.exists()

    def test_ordem_do_arrastar_e_soltar_vale_ao_salvar(self, operador, cenario):
        """O formulário chega na ordem do HTML, mas o campo ORDER (do arrastar) manda."""
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(
            ("Londrina/PR", _local(20, 16)), ("Ponta Grossa/PR", _local(20, 8)),
            volta=_local(21, 15)))
        dados.update({"destino-0-ORDER": "2", "destino-1-ORDER": "1"})
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 302, r.content.decode()[:600]
        assert list(oficio.trechos.order_by("ordem").values_list("destino__nome", flat=True)) \
            == ["Ponta Grossa", "Londrina", "Curitiba"]
        primeiro = oficio.trechos.order_by("ordem").first()
        assert primeiro.origem.nome == "Curitiba"

    def test_destino_removido_sai_do_roteiro(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(
            ("Ponta Grossa/PR", _local(20, 8)), ("Londrina/PR", _local(20, 16)),
            volta=_local(21, 15)))
        dados["destino-1-DELETE"] = "on"
        assert operador.post(reverse("viagens:editar", args=[oficio.pk]),
                             dados).status_code == 302
        assert list(oficio.trechos.order_by("ordem").values_list("destino__nome", flat=True)) \
            == ["Ponta Grossa", "Curitiba"]

    def test_sede_trocada_vale_para_ida_e_volta(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(("Ponta Grossa/PR", _local(20, 8)),
                                                   volta=_local(21, 15), sede="Londrina/PR"))
        assert operador.post(reverse("viagens:editar", args=[oficio.pk]),
                             dados).status_code == 302
        oficio.refresh_from_db()
        ida, volta = oficio.trechos.order_by("ordem")
        assert oficio.sede.nome == "Londrina"
        assert ida.origem.nome == "Londrina" and volta.destino.nome == "Londrina"
        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        assert 'name="sede-cidade"' in html and 'value="Londrina/PR"' in html

    def test_reabrir_mostra_tempos_e_chegada_gravados(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **_itinerario(("Ponta Grossa/PR", _local(20, 8)),
                                                   volta=_local(21, 15), viagem="01:45",
                                                   adicional="00:15"))
        operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        html = operador.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
        chegada = timezone.localtime(oficio.trechos.order_by("ordem").first().chegada_em)
        assert 'name="destino-0-tempo_viagem" value="01:45"' in html
        assert 'name="destino-0-tempo_adicional" value="00:15"' in html
        assert chegada.strftime("%d/%m/%Y %H:%M") in html
        assert 'data-rota-url="/viagens/api/rota/"' in html

    def test_duracao_invalida_volta_com_mensagem(self, operador, cenario):
        oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
        dados = _post_edicao(oficio, **{"destino-0-tempo_viagem": "abc"})
        r = operador.post(reverse("viagens:editar", args=[oficio.pk]), dados)
        assert r.status_code == 422 and "hh:mm" in r.content.decode()
