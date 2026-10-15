"""Modelos de OS (domínio puro): as etapas distribuídas nos dias da viagem e do evento, os
marcadores dos textos e a montagem dos itens (funções primeiro, depois os dias)."""

from __future__ import annotations

from datetime import date, time

import pytest

from gestao.viagens.dominio import modelo_os as m
from gestao.viagens.dominio import ordem_servico as os_


def d(dia: int) -> date:
    return date(2026, 5, dia)


AMBOS = frozenset({"ida_e_antes", "depois_e_volta"})


def nomes(etapas):
    return [(e.nome, e.inicio.day, e.fim.day) for e in etapas]


class TestDistribuirEtapas:
    def test_viagem_3_a_8_com_evento_5_a_6(self):
        assert nomes(m.distribuir_etapas(d(3), d(8), d(5), d(6), combinados=AMBOS)) == [
            ("ida", 3, 3), ("antes", 4, 4), ("evento", 5, 6), ("depois", 7, 7), ("volta", 8, 8)]

    def test_vespera_e_dia_seguinte_usam_os_combinados(self):
        assert nomes(m.distribuir_etapas(d(4), d(7), d(5), d(6), combinados=AMBOS)) == [
            ("ida_e_antes", 4, 4), ("evento", 5, 6), ("depois_e_volta", 7, 7)]

    def test_sem_texto_combinado_saem_ida_e_volta_simples(self):
        assert nomes(m.distribuir_etapas(d(4), d(7), d(5), d(6))) == [
            ("ida", 4, 4), ("evento", 5, 6), ("volta", 7, 7)]

    def test_operacao_policial_17_18_19(self):
        assert nomes(m.distribuir_etapas(d(17), d(19), d(18), d(18))) == [
            ("ida", 17, 17), ("evento", 18, 18), ("volta", 19, 19)]

    def test_tudo_no_mesmo_dia_so_evento(self):
        assert nomes(m.distribuir_etapas(d(18), d(18), d(18), d(18), combinados=AMBOS)) == [
            ("evento", 18, 18)]

    def test_saida_no_dia_do_evento_nao_tem_ida(self):
        assert nomes(m.distribuir_etapas(d(5), d(7), d(5), d(6))) == [
            ("evento", 5, 6), ("volta", 7, 7)]

    def test_sem_evento_a_viagem_inteira_e_evento(self):
        assert nomes(m.distribuir_etapas(d(3), d(8))) == [("evento", 3, 8)]

    def test_evento_com_fim_vazio_e_de_um_dia(self):
        assert nomes(m.distribuir_etapas(d(3), d(5), d(4))) == [
            ("ida", 3, 3), ("evento", 4, 4), ("volta", 5, 5)]

    def test_evento_fora_da_viagem_e_erro(self):
        with pytest.raises(ValueError):
            m.distribuir_etapas(d(4), d(7), d(2), d(3))


A = os_.Pessoa(1, "Ana Lima", "Agente de Polícia Judiciária")
B = os_.Pessoa(2, "Bruno Rocha", "Agente de Polícia Judiciária")
CAMINHAO = m.Modelo(
    nome="Caminhão", referencia="Deslocamento - Caminhão de apoio",
    textos={"ida": "O deslocamento {equipe} para {municipio} {data}, para {motivo}.",
            "ida_e_antes": "", "antes": "Que a equipe faça a montagem {data}.",
            "evento": "Que a equipe permaneça em {destino} {data} {hora}.",
            "depois": "Que a equipe desmonte {data}.", "depois_e_volta": "",
            "volta": "Que a equipe retorne a {sede} {data}."},
    funcoes=(m.Funcao("conducao", "Condução", "Que {servidores} conduza o caminhão."),
             m.Funcao("apoio", "Apoio", "Que {servidores} preste apoio.")),
    justificativas=("Just. 1",), finalidade="Fim.")


def dados(**extra):
    base = {"destinos": ["Londrina/PR"], "inicio": d(3), "fim": d(8), "evento_inicio": d(5),
            "evento_fim": d(6), "motivo": "A Feira", "equipe": [A, B],
            "funcoes": {1: "conducao", 2: "apoio"}, "sede": "Curitiba/PR"}
    return os_.DadosOS(**{**base, **extra})


class TestMarcadores:
    def test_lista_os_marcadores(self):
        assert m.marcadores("x {equipe} y {data}") == {"equipe", "data"}

    def test_invalidos(self):
        assert m.marcadores_invalidos("{data} {foo}", m.MARCADORES_FUNCAO) == {"data", "foo"}

    @pytest.mark.parametrize("ini,fim,texto", [
        (3, 3, "no dia 3 de maio de 2026"), (5, 6, "nos dias 5 e 6 de maio de 2026"),
        (5, 7, "nos dias 5 a 7 de maio de 2026")])
    def test_data_da_etapa(self, ini, fim, texto):
        assert m.data_da_etapa(m.Etapa("evento", d(ini), d(fim))) == texto

    def test_data_da_etapa_em_meses_diferentes(self):
        assert m.data_da_etapa(m.Etapa("evento", date(2026, 5, 30), date(2026, 6, 2))) == (
            "nos dias 30 de maio de 2026 a 2 de junho de 2026")

    def test_hora(self):
        assert m.hora_no_texto(time(5, 0)) == "às 05h00min"
        assert m.hora_no_texto(None) == ""

    def test_romano(self):
        assert [m.romano(n) for n in (1, 4, 9, 14, 40)] == ["I", "IV", "IX", "XIV", "XL"]

    def test_modelo_sabe_se_usa_hora_e_quais_combinados_tem(self):
        assert not CAMINHAO.usa_hora or "{hora}" in CAMINHAO.textos["evento"]
        assert CAMINHAO.combinados == frozenset()
        com = m.Modelo(**{**CAMINHAO.__dict__,
                          "textos": {**CAMINHAO.textos, "ida_e_antes": "x {data}"}})
        assert com.combinados == frozenset({"ida_e_antes"})


class TestItens:
    def test_funcoes_primeiro_depois_os_dias(self):
        t = m.itens_da_os(dados(), CAMINHAO)
        assert t.referencia == "Deslocamento - Caminhão de apoio"
        assert t.itens == [
            "Que Ana Lima conduza o caminhão.",
            "Que Bruno Rocha preste apoio.",
            "O deslocamento dos agentes de polícia judiciária Ana Lima e Bruno Rocha para o "
            "município de Londrina/PR no dia 3 de maio de 2026, para a Feira.",
            "Que a equipe faça a montagem no dia 4 de maio de 2026.",
            "Que a equipe permaneça em Londrina/PR nos dias 5 e 6 de maio de 2026.",
            "Que a equipe desmonte no dia 7 de maio de 2026.",
            "Que a equipe retorne a Curitiba/PR no dia 8 de maio de 2026."]
        assert t.justificativas == ["Just. 1"]
        assert t.finalidade == "Fim."

    def test_funcao_sem_ninguem_nao_sai_e_varios_nomes_juntam(self):
        t = m.itens_da_os(dados(funcoes={1: "apoio", 2: "apoio"}), CAMINHAO)
        assert t.itens[0] == "Que Ana Lima e Bruno Rocha preste apoio."
        assert "conduza" not in " ".join(t.itens)

    def test_hora_entra_quando_existe(self):
        assert m.itens_da_os(dados(hora=time(5, 0)), CAMINHAO).itens[4].endswith(
            "nos dias 5 e 6 de maio de 2026 às 05h00min.")

    def test_texto_combinado_quando_o_modelo_tem(self):
        modelo = m.Modelo(**{**CAMINHAO.__dict__,
                             "textos": {**CAMINHAO.textos,
                                        "ida_e_antes": "Ida e montagem {data}."}})
        itens = m.itens_da_os(dados(inicio=d(4)), modelo).itens
        assert "Ida e montagem no dia 4 de maio de 2026." in itens
        assert not any(i.startswith("O deslocamento") for i in itens)

    def test_servidores_nas_etapas_e_varios_destinos(self):
        modelo = m.Modelo(**{**CAMINHAO.__dict__,
                             "textos": {**CAMINHAO.textos,
                                        "ida": "Que o policial {servidores} vá a {municipio}."}})
        itens = m.itens_da_os(dados(destinos=["Londrina/PR", "Maringá/PR"]), modelo).itens
        assert "Que o policial Ana Lima e Bruno Rocha vá a os municípios de Londrina/PR e " \
               "Maringá/PR." in itens

    def test_sem_periodo_nao_ha_itens_de_dias(self):
        t = m.itens_da_os(dados(inicio=None, fim=None, evento_inicio=None, evento_fim=None),
                          CAMINHAO)
        assert len(t.itens) == 2


class TestPendencias:
    def test_sem_funcao_sem_hora_sem_periodo(self):
        modelo = m.Modelo(**{**CAMINHAO.__dict__,
                             "textos": {**CAMINHAO.textos, "evento": "{hora}"}})
        assert m.faltam_para_o_modelo(
            dados(funcoes={}, hora=None, inicio=None, fim=None), modelo) == [
            "período", "função da equipe", "horário do briefing"]

    def test_completo(self):
        assert m.faltam_para_o_modelo(dados(hora=time(5)), CAMINHAO) == []

    def test_sem_equipe_nao_cobra_funcao(self):
        assert m.faltam_para_o_modelo(dados(equipe=[], funcoes={}, hora=time(5)),
                                      CAMINHAO) == []


class TestConcordancia:
    MODELO = m.Modelo(
        nome="X", referencia="R",
        textos={"ida": "", "ida_e_antes": "", "antes": "",
                "evento": "Que {o policial|os policiais} {servidores} {acompanhe|acompanhem} "
                          "{data}.",
                "depois": "", "depois_e_volta": "", "volta": ""},
        funcoes=(m.Funcao("conducao", "Condução",
                          "O deslocamento {equipe}, na função de {condutor|condutores}, "
                          "{responsável|responsáveis} pelo veículo."),))

    def test_um_servidor_fica_no_singular(self):
        itens = m.itens_da_os(dados(equipe=[A], funcoes={1: "conducao"}, inicio=d(5), fim=d(5),
                                    evento_inicio=None, evento_fim=None), self.MODELO).itens
        assert itens == [
            "O deslocamento do agente de polícia judiciária Ana Lima, na função de condutor, "
            "responsável pelo veículo.",
            "Que o policial Ana Lima acompanhe no dia 5 de maio de 2026."]

    def test_dois_servidores_vao_para_o_plural(self):
        itens = m.itens_da_os(dados(funcoes={1: "conducao", 2: "conducao"}, inicio=d(5),
                                    fim=d(5), evento_inicio=None, evento_fim=None),
                              self.MODELO).itens
        assert itens == [
            "O deslocamento dos agentes de polícia judiciária Ana Lima e Bruno Rocha, na função "
            "de condutores, responsáveis pelo veículo.",
            "Que os policiais Ana Lima e Bruno Rocha acompanhem no dia 5 de maio de 2026."]

    def test_marcadores_ignoram_as_alternativas(self):
        assert m.marcadores("{o policial|os policiais} {servidores}") == {"servidores"}
