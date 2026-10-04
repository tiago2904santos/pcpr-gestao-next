"""Conferência da via assinada (domínio puro): carimbos, número, protocolo e nomes."""

from __future__ import annotations

from datetime import datetime

from gestao.viagens.dominio import conferencia as c


def test_carimbo_do_eprotocolo():
    texto = ("Assinatura Avançada realizada por: Maria Exemplo (XXX.033.259-XX) em 24/09/2026 "
             "11:13 Local: DPC.\nInserido ao protocolo 26.635.814-8 por: José em: 24/09/2026.")
    [a] = c.carimbos(texto)
    assert a.nome == "Maria Exemplo" and a.origem == "eprotocolo"
    assert a.quando == datetime(2026, 9, 24, 11, 13)


def test_carimbo_icp_e_govbr():
    icp = ("Assinado de forma digital por JOAO DA SILVA:12345678901 "
           "Dados: 2026.09.24 10:30:00 -03'00'")
    gov = "Documento assinado digitalmente ANA PEREIRA Data: 25/09/2026 08:05:00-0300"
    nomes = {(a.nome, a.quando) for a in c.carimbos(f"{icp}\n{gov}")}
    assert ("JOAO DA SILVA", datetime(2026, 9, 24, 10, 30)) in nomes
    assert ("ANA PEREIRA", datetime(2026, 9, 25, 8, 5)) in nomes


def test_campo_vale_mais_que_carimbo_e_resumo():
    campo = c.Assinante("Fulano de Tal", datetime(2026, 9, 24, 10, 30), "certificado")
    r = c.conferir("Assinado de forma digital por OUTRO NOME Dados: 2026.09.24",
                   [campo], c.Esperado(), paginas=1)
    assert r.assinado and r.assinante == campo
    assert r.resumo() == "Assinado digitalmente por Fulano de Tal em 24/09/2026 10:30."


def test_sem_assinatura():
    r = c.conferir("OFÍCIO Nº 012/2026 texto qualquer", [], c.Esperado(numero="12/2026"),
                   paginas=1)
    assert not r.assinado and r.avisos == []
    assert r.resumo() == "Este PDF não tem assinatura digital reconhecível."


def test_numero_de_outro_documento():
    r = c.conferir("Ofício nº 13/2026 ...", [], c.Esperado(numero="12/2026", rotulo="ofício"),
                   paginas=1)
    assert r.avisos == ["O número neste PDF é 013/2026, mas você está anexando no ofício "
                        "012/2026."]


def test_protocolo_diferente_e_rg_ignorado():
    texto = "RG nº: 12.345.678-9 Protocolo 26.635.814-8"
    assert c.protocolos_no_texto(texto) == ["266358148"]
    r = c.conferir(texto, [], c.Esperado(protocolo="26.613.666-8", rotulo="ofício"), paginas=1)
    assert r.avisos == ["O protocolo neste PDF é 26.635.814-8, mas o ofício é do protocolo "
                        "26.613.666-8."]


def test_nome_que_falta_sem_acento_e_ligadura():
    r = c.conferir("TERMO ... JOSÉ DA CONCEIÇÃO ... Ceﬁel", [],
                   c.Esperado(nomes=["Jose da Conceicao", "Beltrano Ausente"]), paginas=1)
    assert r.avisos == ["O nome Beltrano Ausente não aparece neste PDF."]


def test_so_imagem_e_ilegivel():
    r = c.conferir("", [], c.Esperado(numero="1/2026"), paginas=2)
    assert r.sem_texto and "só imagem" in r.avisos[0]
    r = c.conferir("", [], c.Esperado(), paginas=0, legivel=False)
    assert r.avisos == ["Não foi possível ler o PDF para conferir se é o documento certo."]


def test_json_guardado_na_via():
    r = c.conferir("", [c.Assinante("X", None, "campo")], c.Esperado(), paginas=0)
    dados = r.como_json()
    assert dados["assinado"] and dados["assinantes"][0]["nome"] == "X"
    assert dados["resumo"] == "Assinado digitalmente por X."


def test_cpf_mascarado_quebrado_em_duas_linhas():
    """A extração do PDF quebra a linha no meio do CPF: "(XXX.\n033.259-XX)"."""
    [a] = c.carimbos("Assinatura Avançada realizada por: Maria Exemplo (XXX.\n033.259-XX) em "
                     "24/09/2026 11:13")
    assert a.nome == "Maria Exemplo"
