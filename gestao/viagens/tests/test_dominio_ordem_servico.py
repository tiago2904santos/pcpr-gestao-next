"""Textos da Ordem de Serviço (domínio puro). Paridade com o contexto do documento da
referência: equipe agrupada por cargo, plural do cargo, períodos e um texto por tipo."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.viagens.dominio import ordem_servico as os_

A = os_.Pessoa(1, "Ana Lima", "Agente de Polícia Judiciária")
B = os_.Pessoa(2, "Bruno Rocha", "Agente de Polícia Judiciária")
C = os_.Pessoa(3, "Carla Duarte", "Escrivão de Polícia")
D = os_.Pessoa(4, "Diego Sem Cargo", "")


class TestEquipeNoTexto:
    def test_um_so(self):
        assert os_.equipe_no_texto([A]) == "do agente de polícia judiciária Ana Lima"

    def test_grupos_por_cargo_com_plural_e_artigos(self):
        texto = os_.equipe_no_texto([C, B, A])
        assert texto == ("dos agentes de polícia judiciária Ana Lima e Bruno Rocha e o escrivão "
                         "de polícia Carla Duarte")

    def test_sem_cargo_vai_por_ultimo_so_com_o_nome(self):
        assert os_.equipe_no_texto([D, A]).endswith("e Diego Sem Cargo")

    def test_sem_equipe(self):
        assert os_.equipe_no_texto([]) == "da equipe"

    @pytest.mark.parametrize("cargo,plural", [
        ("Escrivão de Polícia", "escrivães de polícia"),
        ("Delegado de Polícia", "delegados de polícia"),
        ("Papiloscopista", "papiloscopistas"),
        ("Investigador PC", "investigadores PC"),
    ])
    def test_plural_do_cargo(self, cargo, plural):
        assert os_.cargo_no_texto(cargo, plural=True) == plural


class TestPeriodo:
    @pytest.mark.parametrize("inicio,fim,texto", [
        (date(2026, 7, 10), None, "no dia 10 de julho de 2026"),
        (date(2026, 7, 10), date(2026, 7, 12), "nos dias 10 a 12 de julho de 2026"),
        (date(2026, 7, 30), date(2026, 8, 2), "nos dias 30 de julho de 2026 a 2 de agosto de 2026"),
    ])
    def test_extenso(self, inicio, fim, texto):
        assert os_.periodo_por_extenso(inicio, fim) == texto


class TestTextosPorTipo:
    def _dados(self, **extra):
        base = {"destinos": ["Londrina/PR"], "inicio": date(2026, 7, 10),
                "fim": date(2026, 7, 12), "motivo": "cobertura do evento", "equipe": [A, C]}
        return os_.DadosOS(**{**base, **extra})

    def test_padrao(self):
        t = os_.textos_da_os(self._dados())
        assert t["referencia"] == "Diligências"
        assert t["determinacao"] == (
            "O deslocamento do agente de polícia judiciária Ana Lima e o escrivão de polícia "
            "Carla Duarte para o município de Londrina/PR, nos dias 10 a 12 de julho de 2026, "
            "para realizar cobertura do evento.")
        assert t["competencias"] == [] and t["justificativas"] == []

    def test_operacao_um_dia_posterior(self):
        t = os_.textos_da_os(self._dados(tipo=os_.OPERACAO_RETORNO_POSTERIOR))
        assert t["referencia"] == "Deslocamento - Operação policial com um dia posterior"
        assert "operação policial relacionada a cobertura do evento" in t["determinacao"]
        assert len(t["justificativas"]) == 1

    def test_caminhao_sem_funcoes_volta_ao_padrao(self):
        t = os_.textos_da_os(self._dados(tipo=os_.CAMINHAO))
        assert t["referencia"] == "Diligências"

    def test_caminhao_com_funcoes(self):
        t = os_.textos_da_os(self._dados(tipo=os_.CAMINHAO,
                                         funcoes={1: os_.CONDUCAO, 3: os_.APOIO}))
        assert t["referencia"] == "Deslocamento - Caminhão de apoio"
        assert t["competencias"][0].startswith("Ana Lima – conduzir a Unidade Móvel")
        assert "entre Curitiba e Londrina/PR" in t["competencias"][1]
        assert len(t["justificativas"]) == 2

    def test_cerimonial_com_varios_na_mesma_funcao(self):
        t = os_.textos_da_os(self._dados(tipo=os_.CERIMONIAL_ANTECIPADO, equipe=[A, B],
                                         funcoes={1: os_.APOIO, 2: os_.APOIO}))
        assert t["competencias"] == [
            "Ana Lima e Bruno Rocha: prestar apoio às atividades de Cerimonial, auxiliando na "
            "organização do ambiente, recepção das autoridades e execução dos procedimentos "
            "protocolares"]

    def test_sem_motivo_e_sem_destino(self):
        t = os_.textos_da_os(os_.DadosOS())
        assert "destino informado" in t["determinacao"]
        assert "atuação na atividade institucional designada" in t["determinacao"]


class TestRevisaoDeUX:
    @pytest.mark.parametrize("motivo,texto", [
        ("Capacitação de equipes em São Paulo.", "capacitação de equipes em São Paulo"),
        ("PCPR na Comunidade.", "PCPR na Comunidade"),
        ("  cobertura do evento ;", "cobertura do evento"),
        ("", ""),
    ])
    def test_motivo_entra_no_meio_da_frase(self, motivo, texto):
        assert os_.motivo_no_texto(motivo) == texto

    def test_varios_destinos_no_plural(self):
        t = os_.textos_da_os(os_.DadosOS(destinos=["Londrina/PR", "Maringá/PR"],
                                         motivo="X", equipe=[A]))
        assert "para os municípios de Londrina/PR e Maringá/PR" in t["determinacao"]

    def test_faltam_funcoes(self):
        assert os_.faltam_funcoes(os_.DadosOS(tipo=os_.MICROONIBUS, equipe=[A]))
        assert not os_.faltam_funcoes(os_.DadosOS(tipo=os_.MICROONIBUS, equipe=[A],
                                                  funcoes={1: os_.CONDUCAO}))
        assert not os_.faltam_funcoes(os_.DadosOS(tipo=os_.PADRAO, equipe=[A]))
