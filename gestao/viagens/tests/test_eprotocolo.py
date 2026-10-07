"""Formato copiável do RS-01: apenas domínio puro, sem fixtures ou banco."""

from __future__ import annotations

from datetime import date

import pytest

from gestao.viagens.dominio.assunto import resolver_assunto
from gestao.viagens.dominio.eprotocolo import dados_eprotocolo


def test_cinco_campos_reproduzem_o_formato_legado_para_oficio_ficticio():
    assunto = resolver_assunto(date(2026, 10, 7), date(2026, 10, 20))
    resultado = dados_eprotocolo(
        numero="01/2026", protocolo="123456789", assunto_linha=assunto.linha,
        assunto_rotulo=assunto.rotulo, destinos=["Curitiba/PR", "Londrina/PR"],
        saida=date(2026, 10, 20), retorno=date(2026, 10, 22),
        servidores=["Bruno Exemplo", "Ana Exemplo"], motivo="Apoio à operação fictícia.",
    )
    assert [(c.rotulo, c.valor) for c in resultado.campos] == [
        ("Interessados", "Ana Exemplo, Bruno Exemplo"),
        ("Assunto", "Solicitação de autorização e concessão de diárias. (Autorização)"),
        ("Nº/Ano do ofício", "01/2026"),
        ("Protocolo", "12.345.678-9"),
        ("Detalhamento", "OFÍCIO Nº 01/2026 - SOLICITAÇÃO DE AUTORIZAÇÃO E CONCESSÃO "
         "DE DIÁRIAS - DESTINO: CURITIBA/PR, LONDRINA/PR - PERÍODO: 20/10/2026 a "
         "22/10/2026 - SERVIDORES: Ana Exemplo, Bruno Exemplo\nApoio à operação fictícia."),
    ]


@pytest.mark.parametrize("saida,retorno,esperado", [
    (date(2026, 10, 20), None, "20/10/2026"),
    (date(2026, 10, 20), date(2026, 10, 20), "20/10/2026"),
    (date(2026, 12, 31), date(2027, 1, 2), "31/12/2026 a 02/01/2027"),
    (None, date(2026, 10, 20), ""), (None, None, ""),
])
def test_periodo_usa_datas_locais_sem_inventar_saida(saida, retorno, esperado):
    resultado = dados_eprotocolo(saida=saida, retorno=retorno)
    if esperado:
        assert resultado.detalhamento == f"OFÍCIO - PERÍODO: {esperado}"
    else:
        assert resultado.detalhamento == "OFÍCIO"


def test_nomes_ordenados_sem_mutar_lista_nem_eliminar_homonimos():
    nomes = ["Zélia Exemplo", "Ana Exemplo", "Ana Exemplo", "  Bruno Exemplo  ", ""]
    resultado = dados_eprotocolo(servidores=nomes)
    assert resultado.campos[0].valor == "Ana Exemplo, Ana Exemplo, Bruno Exemplo, Zélia Exemplo"
    assert nomes == ["Zélia Exemplo", "Ana Exemplo", "Ana Exemplo", "  Bruno Exemplo  ", ""]


@pytest.mark.parametrize("entrada,esperado", [
    ("123456789", "12.345.678-9"), ("12.345.678-9", "12.345.678-9"),
    ("", ""), ("123", "123"), ("ABCDEFGHI", "ABCDEFGHI"),
])
def test_protocolo_preserva_mascara_e_nao_inventa_digitos(entrada, esperado):
    assert dados_eprotocolo(protocolo=entrada).campos[3].valor == esperado


def test_campos_ausentes_nao_geram_separadores_ou_rotulos_sem_valor_no_detalhamento():
    resultado = dados_eprotocolo()
    assert [c.valor for c in resultado.campos] == ["", "", "", "", "OFÍCIO"]
    assert resultado.copiar_tudo == (
        "Interessados: \nAssunto: \nNº/Ano do ofício: \nProtocolo: \nDetalhamento: OFÍCIO")


def test_motivo_preserva_quebras_de_linha_e_o_texto_institucional():
    motivo = "Linha um.\nLinha dois com acentos: ação."
    assert dados_eprotocolo(numero="07/2026", motivo=motivo).detalhamento == (
        f"OFÍCIO Nº 07/2026\n{motivo}")


def test_rotulo_do_assunto_nao_entra_no_detalhamento():
    resultado = dados_eprotocolo(
        assunto_linha="Solicitação de convalidação e concessão de diárias.",
        assunto_rotulo="(Complementar)",
    )
    assert resultado.campos[1].valor.endswith(". (Complementar)")
    assert resultado.detalhamento == "OFÍCIO - SOLICITAÇÃO DE CONVALIDAÇÃO E CONCESSÃO DE DIÁRIAS"


def test_destinos_preservam_ordem_repeticoes_e_limite_da_fonte_local():
    destinos = ["Londrina/PR", "Curitiba/PR", "Londrina/PR"]
    resultado = dados_eprotocolo(destinos=destinos)
    assert resultado.detalhamento == "OFÍCIO - DESTINO: LONDRINA/PR, CURITIBA/PR, LONDRINA/PR"
    muitos = dados_eprotocolo(destinos=[f"Destino {i}/PR" for i in range(101)])
    assert "DESTINO 99/PR +1" in muitos.detalhamento
    assert "DESTINO 100/PR" not in muitos.detalhamento


def test_copiar_tudo_reutiliza_os_valores_sem_resumir_motivo():
    resultado = dados_eprotocolo(numero="42/2026", protocolo="123456789", motivo="Linha 1\nLinha 2")
    assert resultado.copiar_tudo == "\n".join(f"{c.rotulo}: {c.valor}" for c in resultado.campos)
    assert resultado.copiar_tudo.endswith("Detalhamento: OFÍCIO Nº 42/2026\nLinha 1\nLinha 2")
