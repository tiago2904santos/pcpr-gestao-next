"""E2E: cadastros mantidos em tela (módulo 2) — fluxos completos pelo navegador.

Paridade com a referência: só o nome (servidor) / a placa (viatura) são obrigatórios,
cadastro incompleto sinalizado, motoristas por busca, excluir só sem vínculos, diária com a
prévia dos percentuais. Dados fictícios.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Servidor, TabelaDiaria, Viatura

from .conftest import entrar

pytestmark = pytest.mark.e2e


def test_servidor_nasce_incompleto_e_e_completado(logado):
    pg = logado
    pg.goto("/cadastros/")
    pg.get_by_role("link", name="Servidores", exact=True).first.click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Servidores")
    pg.get_by_role("button", name="Novo servidor").first.click()
    janela = pg.get_by_role("dialog", name="Novo servidor")
    janela.get_by_label("Nome completo").fill("Paula Fictícia Andrade")
    janela.get_by_role("button", name="Cadastrar servidor").click()
    expect(pg.locator(".toast")).to_contain_text("falta cargo e CPF")
    pg.get_by_role("link", name=re.compile("Incompletos")).click()
    pg.get_by_role("link", name="Paula Fictícia Andrade").click()
    janela = pg.get_by_role("dialog", name=re.compile("Editar Paula"))
    # Máscaras: CPF e telefone saem formatados enquanto se digita.
    janela.get_by_label("CPF").press_sequentially("52998224725")
    expect(janela.get_by_label("CPF")).to_have_value("529.982.247-25")
    janela.get_by_label("Telefone").press_sequentially("41999990000")
    expect(janela.get_by_label("Telefone")).to_have_value("(41) 99999-0000")
    janela.get_by_role("combobox", name="Cargo").click()
    janela.get_by_role("option", name="Escrivão de Polícia").click()
    janela.get_by_role("button", name="Salvar alterações").click()
    expect(pg.locator(".toast")).to_contain_text("atualizado")
    s = Servidor.objects.get(nome="Paula Fictícia Andrade")
    assert s.completo and s.cpf == "52998224725" and s.telefone == "41999990000"
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_viatura_com_motoristas_por_busca(logado):
    pg = logado
    pg.goto("/cadastros/viaturas/")
    pg.get_by_role("button", name="Nova viatura").first.click()
    janela = pg.get_by_role("dialog", name="Nova viatura")
    janela.get_by_label("Placa").press_sequentially("zzt-1a23")
    expect(janela.get_by_label("Placa")).to_have_value("ZZT1A23")
    janela.get_by_label("Modelo").fill("Fiat Cronos")
    # Sem a legenda "Motoristas habituais" (um grupo só na janela), o rótulo do campo
    # é que diz o que a busca alimenta.
    busca = janela.get_by_role("combobox", name="Motoristas habituais")
    for nome in ("Isabela", "Bruno"):
        busca.fill(nome.lower())
        janela.get_by_role("option", name=re.compile(nome)).first.click()
    escolhidos = janela.locator(".multiescolha__item")
    expect(escolhidos).to_have_count(2)
    # Escolher de novo quem já está não repete; remover tira.
    busca.fill("isabela")
    janela.get_by_role("option", name=re.compile("Isabela")).first.click()
    expect(escolhidos).to_have_count(2)
    janela.get_by_role("button", name=re.compile("Remover Bruno")).click()
    expect(escolhidos).to_have_count(1)
    janela.get_by_role("button", name="Cadastrar viatura").click()
    expect(pg.locator(".toast")).to_contain_text("ZZT1A23")
    v = Viatura.objects.get(placa="ZZT1A23")
    assert [m.nome for m in v.motoristas.all()] == ["Isabela Prado Cavalcanti"]
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_excluir_sem_vinculo_e_recusa_com_vinculo(logado):
    pg = logado
    Servidor.objects.create(nome="Sem Vínculo Fictício")
    pg.goto("/cadastros/servidores/?q=vinculo")
    pg.get_by_role("button", name="Ações de Sem Vínculo Fictício").click()
    pg.get_by_role("menuitem", name="Excluir").click()
    confirmar = pg.get_by_role("dialog", name="Excluir servidor?")
    confirmar.get_by_role("button", name="Excluir").click()
    expect(pg.locator(".toast")).to_contain_text("excluído")
    assert not Servidor.objects.filter(nome="Sem Vínculo Fictício").exists()
    # Cargo usado por servidores: "Excluir" nem é oferecido; a linha diz onde é usado e o
    # menu oferece Desativar.
    pg.goto("/cadastros/cargos/?q=escrivao")
    expect(pg.locator(".registro").first).to_contain_text("servidor")
    pg.get_by_role("button", name=re.compile("Ações de “Escrivão")).click()
    expect(pg.get_by_role("menuitem", name="Excluir")).to_have_count(0)
    pg.get_by_role("menuitem", name="Desativar").click()
    expect(pg.locator(".toast")).to_contain_text("desativado")
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_gestor_cadastra_vigencia_com_previa(pagina):
    pg = pagina
    entrar(pg, "gestor")
    pg.goto("/cadastros/diarias/")
    pg.get_by_role("button", name="Nova vigência").first.click()
    janela = pg.get_by_role("dialog", name="Nova vigência")
    janela.get_by_role("combobox", name="Faixa").click()
    janela.get_by_role("option", name="Capital").click()
    janela.get_by_role("textbox", name="Vigente a partir de").fill("01/01/2030")
    janela.get_by_label("Diária de 24 horas").fill("290.55")
    expect(janela.locator("[data-diaria-percentual='15']")).to_have_text(re.compile(r"43,58"))
    expect(janela.locator("[data-diaria-percentual='30']")).to_have_text(re.compile(r"87,17"))
    janela.get_by_role("button", name="Cadastrar vigência").click()
    expect(pg.locator(".toast")).to_contain_text("cadastrada")
    assert TabelaDiaria.objects.filter(faixa="capital", vigente_desde__year=2030).exists()
    assert pg.erros_console == []  # type: ignore[attr-defined]
