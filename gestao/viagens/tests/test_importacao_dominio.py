import pytest

from gestao.viagens.dominio.importacao import (
    Destino,
    Parte,
    identificar,
    identificar_conjunto,
    protocolos,
    separar,
    tipo_do_texto,
)


@pytest.mark.parametrize(
    ("texto", "tipo"),
    [
        ("PCPR\nOfício nº 120/2026\nEncaminho despacho", "oficio"),
        ("DESPACHO\nReferente ao Ofício 120/2026", "despacho"),
        ("RELATÓRIO TÉCNICO\nOfício 120/2026", "rt_assinado"),
        ("TERMO DE AUTORIZAÇÃO\nAna", "termo"),
        ("ORDEM DE SERVIÇO 21/2026", "ordem"),
        ("Uma carta que menciona um ofício", ""),
    ],
)
def test_titulo(texto, tipo):
    assert tipo_do_texto(texto) == tipo


def test_documentos_mistos_e_assinatura():
    partes = separar(
        [
            "Ofício 120/2026",
            "Assinado por autoridade",
            "DESPACHO\nOfício 120/2026",
            "TERMO DE AUTORIZAÇÃO\nAna Silva",
        ]
    )
    assert [(p.tipo, p.inicio, p.fim) for p in partes] == [
        ("oficio", 1, 2),
        ("despacho", 3, 3),
        ("termo", 4, 4),
    ]


def test_documento_desconhecido_com_titulo_nao_vira_pagina_do_oficio():
    partes = separar(["Ofício 120/2026", "Assinatura da autoridade", "NOTA FISCAL\nRestaurante"])
    assert [(p.tipo, p.inicio, p.fim) for p in partes] == [("oficio", 1, 2), ("", 3, 3)]


def test_nao_adivinhar_ano_ou_ignorar_conflito():
    destinos = [
        Destino("a", "oficio", "A", 120, 2025, "123456789"),
        Destino("b", "oficio", "B", 120, 2026, "234567891"),
    ]
    assert not identificar(Parte(1, 1, "oficio", "Ofício 120"), destinos).chave
    assert identificar(Parte(1, 1, "oficio", "Ofício 120/2026"), destinos).chave == "b"
    assert not identificar(Parte(1, 1, "oficio", "Ofício 120/2026\n12.345.678-9"), destinos).chave
    assert not identificar(
        Parte(1, 1, "oficio", "Ofício 120/2026 e Ofício 120/2025"), destinos
    ).chave
    assert identificar(Parte(1, 1, "oficio", "Ofício 120/25"), destinos).chave == "a"
    assert not identificar(Parte(1, 1, "oficio", "Ofício 120/20266"), destinos).chave


def test_pessoa_com_nome_e_cpf_conflitantes_nao_anexa():
    destinos = [
        Destino("a", "termo", "A", 120, 2026, nome="Ana Silva", cpf="12345678901"),
        Destino("b", "termo", "B", 120, 2026, nome="Bia Souza", cpf="98765432100"),
    ]
    assert identificar(Parte(1, 1, "termo", "Ofício 120/2026\nAna Silva"), destinos).chave == "a"
    assert not identificar(
        Parte(1, 1, "termo", "Ofício 120/2026\nAna Silva\n987.654.321-00"), destinos
    ).chave
    assert not identificar(Parte(1, 1, "termo", "Ana Silva"), destinos).chave


def test_despacho_herda_oficio_do_mesmo_processo_sem_ignorar_conflitos():
    destinos = [
        Destino("oficio:1:", "oficio", "Ofício", 120, 2026),
        Destino("despacho:1:", "despacho", "Despacho", 120, 2026),
    ]
    partes = [
        Parte(1, 1, "oficio", "Ofício 120/2026"),
        Parte(2, 2, "despacho", "DESPACHO\nEncaminhe para providências."),
    ]
    assert identificar_conjunto(partes, destinos)[1].chave == "despacho:1:"
    partes.append(Parte(3, 3, "oficio", "Ofício 140/2026"))
    assert not identificar_conjunto(partes, destinos)[1].chave


def test_rascunho_nao_e_via_assinada_e_contexto_nao_remove_a_restricao():
    destinos = [
        Destino("a", "oficio", "Ofício", 120, 2026),
        Destino("b", "despacho", "Despacho", 120, 2026),
    ]
    assert not identificar(Parte(1, 1, "oficio", "Ofício 120/2026\nMINUTA"), destinos).chave
    partes = [
        Parte(1, 1, "oficio", "Ofício 120/2026"),
        Parte(2, 2, "despacho", "DESPACHO\nRASCUNHO"),
    ]
    assert not identificar_conjunto(partes, destinos)[1].chave


@pytest.mark.parametrize(
    "texto", ["Protocolo nº 123456789", "e-Protocolo: 123456789", "12.345.678-9"]
)
def test_protocolo_formatado_e_por_extenso(texto):
    assert protocolos(texto) == {"123456789"}


def test_termo_com_periodo_por_extenso_e_nome_quebrado():
    destinos = [
        Destino(
            "a",
            "termo",
            "A",
            nome="Ana Maria Silva",
            cpf="12345678901",
            periodo="nos dias 10 até 12 de julho de 2026",
        )
    ]
    p = Parte(
        1, 1, "termo", "TERMO DE AUTORIZAÇÃO\nAna Maria\nSilva\nnos dias 10 até 12 de julho de 2026"
    )
    assert identificar(p, destinos).chave == "a"
    assert not identificar(Parte(1, 1, "termo", p.texto.replace("2026", "2025")), destinos).chave
    destinos.append(
        Destino(
            "b", "termo", "B", nome="Ana Maria Silva", periodo="nos dias 10 até 12 de julho de 2026"
        )
    )
    assert not identificar(p, destinos).chave  # homônimo/evento indistinguível
