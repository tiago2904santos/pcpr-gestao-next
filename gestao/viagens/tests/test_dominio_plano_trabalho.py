"""Domínio do plano de trabalho (6b), sem banco. Os exemplos de diárias são os da
referência (`viagens_planos/tests/test_diarias.py`): sede Curitiba, interior a R$ 290,55."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from gestao.viagens.dominio import plano_trabalho as pt
from gestao.viagens.dominio.diarias import Faixa, ValorVigente
from gestao.viagens.dominio.escrita import cargo_no_plural, legivel, moeda


def _tabelas(_data):
    valores = {Faixa.INTERIOR: "290.55", Faixa.CAPITAL: "335.85", Faixa.BRASILIA: "380.00"}
    return {f: ValorVigente(f, Decimal(v), date(2026, 1, 1)) for f, v in valores.items()}


def _diarias(saida, chegada, destino=("Maringá", "PR"), servidores=6):
    return pt.calcular_diarias(saida=saida, chegada=chegada, destino=destino,
                               servidores=servidores, sede=("Curitiba", "PR"),
                               buscar_tabelas=_tabelas)


class TestDiarias:
    def test_maringa_ao_centavo(self):
        c = _diarias(datetime(2026, 6, 24, 7), datetime(2026, 6, 28, 14))
        assert c.resumo == "4 x 100% + 1 x 15%"
        assert c.por_servidor == Decimal("1205.78") and c.total == Decimal("7234.68")
        c10 = _diarias(datetime(2026, 6, 24, 7), datetime(2026, 6, 28, 14), servidores=10)
        assert c10.total == Decimal("12057.80")

    def test_sarandi_ao_centavo(self):
        c = _diarias(datetime(2026, 6, 23, 7), datetime(2026, 6, 28, 16), ("Sarandi", "PR"), 18)
        assert c.resumo == "5 x 100% + 1 x 30%"
        assert c.por_servidor == Decimal("1539.92") and c.total == Decimal("27718.56")

    def test_faltas_juntas_e_chegada_antes_da_saida(self):
        with pytest.raises(pt.PlanoIncalculavel) as erro:
            pt.calcular_diarias(saida=None, chegada=None, destino=None, servidores=0,
                                sede=("Curitiba", "PR"), buscar_tabelas=_tabelas)
        assert erro.value.mensagens == [
            "Informe data e hora de saída da sede.", "Informe data e hora de chegada na sede.",
            "Informe o destino na identificação.", "Informe o efetivo (cargo e quantidade)."]
        with pytest.raises(pt.PlanoIncalculavel) as erro:
            _diarias(datetime(2026, 6, 28, 7), datetime(2026, 6, 24, 7))
        assert erro.value.mensagens == ["A chegada na sede deve ser depois da saída."]

    def test_sem_tabela_vigente_recusa(self):
        with pytest.raises(pt.PlanoIncalculavel) as erro:
            pt.calcular_diarias(saida=datetime(2026, 6, 24, 7), chegada=datetime(2026, 6, 26, 7),
                                destino=("Maringá", "PR"), servidores=1, sede=("Curitiba", "PR"),
                                buscar_tabelas=lambda d: {})
        assert "Não há valor de diária vigente" in erro.value.mensagens[0]

    def test_texto_do_valor_como_na_referencia(self):
        texto = pt.texto_do_valor("4 x 100% + 1 x 15%", Decimal("1205.78"), Decimal("7234.68"))
        assert texto.startswith(
            "Valor total: R$7.234,68 (sete mil duzentos e trinta e quatro reais")
        assert ("Valor correspondente a 4 x 100% + 1 x 15%, por servidor, no valor unitário de "
                "R$1.205,78 (") in texto


class TestTextos:
    def test_contextualizacao_com_municipio_e_programa(self):
        texto = pt.contextualizacao(["Maringá/PR"], ["PROGRAMA PARANÁ EM AÇÃO"])
        paragrafos = texto.split("\n\n")
        assert len(paragrafos) == 3
        assert "ação itinerante no município de Maringá/PR." in paragrafos[0]
        assert "solicitação formulada pelo Programa Paraná em Ação (Ofício em anexo)" in texto

    def test_sem_destino_nem_programa_ficam_linhas_em_branco(self):
        texto = pt.contextualizacao([], [])
        assert "município de ________." in texto and "pelo ________ (Ofício" in texto

    def test_considera_varios_municipios_sem_repetir(self):
        texto = pt.consideracoes_finais(["Maringá/PR", "Sarandi/PR", "Maringá/PR"])
        assert "no município de Maringá/PR, Sarandi/PR reforça" in texto

    def test_coordenacao_com_genero_e_capitalizacao(self):
        adm = pt.Coordenador("JULIANA VILLELA DE BARROS", "PAPILOSCOPISTA", pt.FEMININO)
        texto = pt.coordenacao(adm, None)
        assert texto.startswith("Fica designada como Coordenadora Administrativa do Plano a "
                                "Papiloscopista Juliana Villela de Barros, a qual ficará")
        op = pt.Coordenador("CAIO PRADO RIBEIRO", "Agente de Polícia Judiciária")
        texto = pt.coordenacao(adm, op)
        assert ("Fica designado como Coordenador Operacional do Evento o Agente de Polícia "
                "Judiciária Caio Prado Ribeiro, o qual") in texto
        assert pt.coordenacao(adm, op, varios_eventos=True).count("Fica designad") == 1
        assert pt.coordenacao(None, None) == ""

    def test_periodos_por_extenso(self):
        assert pt.periodo_por_extenso(date(2026, 6, 25), None) == "25 de junho de 2026"
        assert pt.periodo_por_extenso(date(2026, 6, 25), date(2026, 6, 27)) == (
            "25 a 27 de junho de 2026")
        assert pt.periodo_por_extenso(date(2026, 6, 30), date(2026, 7, 2)) == (
            "30 de junho a 02 de julho de 2026")
        assert pt.periodo_por_extenso(date(2025, 12, 30), date(2026, 1, 2)) == (
            "30 de dezembro de 2025 a 02 de janeiro de 2026")


class TestAtividadesEEfetivo:
    def test_metas_e_recursos_sem_repetir_e_unidade_movel(self):
        a = pt.Atividade("CIN", "Confecção da CIN", "Ampliar o acesso.", "Kit biométrico.")
        b = pt.Atividade("BO", "Boletins", "Ampliar o acesso.", "")
        m = pt.Atividade(pt.UNIDADE_MOVEL, "Unidade móvel", "Descentralizar.", "Ônibus.")
        textos = pt.textos_das_atividades([a, m, b])
        assert textos["atividades"] == "• Boletins\n• Confecção da CIN\n• Unidade móvel"
        assert textos["metas"] == "• Ampliar o acesso.\n• Descentralizar."
        assert textos["recursos"].endswith(pt.RECURSO_UNIDADE_MOVEL)
        assert textos["unidade_movel"] == pt.ESTRUTURA_UNIDADE_MOVEL
        assert pt.textos_das_atividades([a])["unidade_movel"] == ""

    def test_efetivo_no_plural_com_sigla(self):
        linhas = [pt.LinhaEfetivo(6, "Policial Civil", "ASCOM", "Assessoria"),
                  pt.LinhaEfetivo(1, "Papiloscopista"),
                  pt.LinhaEfetivo(2, "Agente de Polícia Judiciária", "DPC", "Divisão"),
                  pt.LinhaEfetivo(0, "Escrivão de Polícia")]
        assert pt.texto_do_efetivo(linhas) == (
            "1 Papiloscopista\n6 Policiais Civis (ASCOM)\n2 Agentes de Polícia Judiciária (DPC)")
        assert pt.efetivo_total(linhas) == 9

    def test_plural_so_do_nucleo_do_cargo(self):
        assert cargo_no_plural("Escrivão de Polícia") == "Escrivães de Polícia"
        assert cargo_no_plural("Policial Civil") == "Policiais Civis"
        assert cargo_no_plural("Delegado") == "Delegados"


class TestPendenciasEFormatos:
    def test_plano_vazio_lista_as_cinco_na_ordem(self):
        falta = pt.pendencias(pt.DadosPlano())
        assert [p.mensagem for p in falta] == [
            "Informe o coordenador administrativo.", "Informe o destino (cidade/UF).",
            "Informe a data do evento.", "Informe o efetivo (cargo e quantidade).",
            "Calcule as diárias (saída e chegada na sede)."]
        assert [p.secao for p in falta] == ["identificacao"] * 3 + ["efetivo"] * 2

    def test_plano_completo_sem_pendencia(self):
        d = pt.DadosPlano(destinos=["Maringá/PR"], inicio=date(2026, 6, 25),
                          coordenador_adm=pt.Coordenador("ANA"),
                          efetivo=[pt.LinhaEfetivo(2, "Agente")], diarias_total=Decimal("10"))
        assert pt.pendencias(d) == []

    def test_numero_e_valores(self):
        assert pt.numero_formatado(7, 2026, "ASCOM") == "07/2026/ASCOM"
        assert pt.numero_formatado(None, 2026) == "—"
        assert moeda(Decimal("1205.78")) == "1.205,78"
        assert legivel("PCPR NA COMUNIDADE") == "PCPR na Comunidade"
