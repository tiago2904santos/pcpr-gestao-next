"""Regras puras da assistência: validador de fatos, esquema dos textos, leitura por regra,
Central de ajuda e assistente determinístico — e o gabarito do AUT-91 inteiro."""

from __future__ import annotations

import pytest

from gestao.assistencia import assistente, conhecimento, ganchos
from gestao.assistencia.avaliacao import rodar
from gestao.assistencia.dominio import leitura, textos
from gestao.assistencia.dominio.validacao import validar_fontes, validar_texto
from gestao.integracoes.ia import esquema


@pytest.mark.parametrize("resultado", rodar.tudo(), ids=lambda r: f"{r.grupo}:{r.nome}")
def test_gabarito_aut_91(resultado):
    assert resultado.passou, resultado.detalhe


def test_validador_aceita_texto_fiel_e_aponta_cada_problema():
    fatos = "[destinos] Destinos: Arapongas/PR\n[periodo] Período: 08/11 a 10/11/2026"
    assert validar_texto("Viagem a Arapongas/PR de 08/11 a 10/11/2026.", fatos=fatos) == []
    erros = validar_texto("Viagem com 3 diárias de R$ 290,55.", fatos=fatos)
    assert any(e.startswith("numero_sem_fonte") for e in erros)
    assert "termo_vedado:diaria" in erros and "termo_vedado:valor_monetario" in erros
    assert validar_fontes([], ["destinos"]) == ["sem_fonte"]
    assert validar_fontes(["inventada"], ["destinos"]) == ["fonte_inexistente"]


def test_termo_vedado_passa_quando_esta_nos_fatos():
    fatos = "[etapa] Conferência: Escolha a viatura."
    assert validar_texto("Falta escolher a viatura.", fatos=fatos) == []


def test_esquema_de_textos_e_fechado():
    e = textos.esquema_textos(("motivo",), ("destinos",), ("lacuna_a",), 100)
    ok = {"textos": [{"campo": "motivo", "texto": "x", "fontes": ["destinos"]}],
          "lacunas": ["lacuna_a"]}
    assert esquema.validar(ok, e) == []
    assert esquema.validar({**ok, "extra": 1}, e)
    assert esquema.validar({"textos": [{"campo": "outro", "texto": "x", "fontes": []}],
                            "lacunas": []}, e)
    assert esquema.validar({"textos": [], "lacunas": ["inventada"]}, e)


def test_validar_textos_recusa_campo_fora_e_repetido():
    dados = {"textos": [{"campo": "motivo", "texto": "Arapongas", "fontes": ["d"]},
                        {"campo": "motivo", "texto": "Arapongas", "fontes": ["d"]},
                        {"campo": "conclusao", "texto": "x", "fontes": ["d"]}]}
    erros = textos.validar_textos(dados, fatos_texto="[d] D: Arapongas", chaves=["d"],
                                  campos_alvo=("motivo",))
    assert "campo_repetido:motivo" in erros and "campo_fora_do_pedido:conclusao" in erros
    assert textos.codigos(["motivo:numero_sem_fonte:37"]) == ["motivo:numero_sem_fonte"]


def test_leitura_confere_que_o_dado_esta_no_texto():
    texto = "21/11 saída às 07:30 para Maringá"
    assert leitura.data_no_texto("2026-11-21", texto)
    assert not leitura.data_no_texto("2026-11-22", texto)
    assert leitura.hora_no_texto("07:30", texto) and not leitura.hora_no_texto("08:00", texto)
    assert leitura.termo_no_texto("Maringa", texto) and not leitura.termo_no_texto("Londrina",
                                                                                      texto)


def test_contexto_versao_ignora_o_que_quem_pediu_escreveu():
    a = ganchos.Contexto("x", (ganchos.Fato("d", "D", "Arapongas"),
                               ganchos.Fato("o", "O", "texto 1", do_pedido=True)))
    b = ganchos.Contexto("x", (ganchos.Fato("d", "D", "Arapongas"),
                               ganchos.Fato("o", "O", "texto 2", do_pedido=True)))
    c = ganchos.Contexto("x", (ganchos.Fato("d", "D", "Maringá"),))
    assert a.versao == b.versao != c.versao
    d = ganchos.Contexto("x", (ganchos.Fato("d", "D", "Arapongas"),), {"motivo": "escrito"})
    assert d.versao != ganchos.Contexto("x", (ganchos.Fato("d", "D", "Arapongas"),)).versao


def test_uso_sem_minimizacao_declarada_e_recusado():
    base = ganchos.uso("assistencia.triagem_modulo")
    from dataclasses import replace

    with pytest.raises(ValueError):
        ganchos.registrar_uso(replace(base, chave="x.sem", dados_excluidos=()))
    with pytest.raises(ValueError):
        ganchos.registrar_uso(replace(base, chave="x.aberto", esquema={"type": "object"}))


def test_todos_os_usos_registrados_declaram_o_que_entra_e_o_que_nao():
    usos = {u.codigo: u for u in ganchos.usos()}
    for codigo in ("AUT-50", "AUT-57", "AUT-58", "AUT-76", "AUT-80", "AUT-81", "AUT-86",
                   "AUT-88", "AUT-89", "AUT-93"):
        u = usos[codigo]
        assert u.campos_permitidos and u.dados_excluidos and u.versao_prompt
        assert u.esquema["additionalProperties"] is False
        assert "distancia" not in str(u.esquema) and "diaria" not in str(u.esquema)
    assert usos["AUT-57"].envolve_documento and usos["AUT-58"].envolve_documento


def test_central_so_mostra_aprovados_e_le_os_cabecalhos():
    artigos = conhecimento.todos()
    assert len(artigos) >= 8 and all(a.situacao == "aprovado" for a in artigos)
    assert {a.natureza for a in artigos} <= set(conhecimento.NATUREZAS)
    assert conhecimento.por_slug("prazo-prestacao").natureza == "regra_do_sistema"
    assert conhecimento.por_slug("nao-existe") is None


def test_assistente_sem_servidor_nao_inventa_situacao():
    r = assistente.responder("Até quando posso sacar a minha diária?", None)
    assert "identificacao" in r.lacunas and "Situação em" not in r.texto
    r2 = assistente.responder("Troque meu telefone cadastrado", 1)
    assert r2.categoria == "recusa"


def test_triagem_valida_modulo_e_sinal():
    from gestao.assistencia.usos_proprios import sinais, validar_triagem

    texto = "Pedido de entrevista de jornalista sobre a operação"
    ctx = ganchos.Contexto("x", (ganchos.Fato("texto", "Demanda", texto),))
    assert sinais(texto, "imprensa") == ["entrevista", "jornalista"]
    assert validar_triagem({"modulo": "imprensa", "sinais": ["Jornalista"], "lacunas": []},
                           ctx) == []
    assert validar_triagem({"modulo": "", "sinais": [], "lacunas": ["sem_sinal"]}, ctx) == []
    assert validar_triagem({"modulo": "outro", "sinais": ["x"], "lacunas": []},
                           ctx) == ["modulo_fora_da_lista"]
    assert "sinal_de_outro_modulo" in validar_triagem(
        {"modulo": "coffee", "sinais": ["operação"], "lacunas": []}, ctx)


def test_usos_sem_obsolescencia_sao_so_os_de_pedido_pessoal_sem_registro():
    sem = {u.chave for u in ganchos.usos() if u.versao_atual is None}
    assert sem == {"assistencia.triagem_modulo"}
