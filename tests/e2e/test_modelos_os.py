"""E2E: o gestor cadastra um modelo de OS com funções e o vê na lista; a tela passa no axe e
não rola na horizontal em 360 e 1440."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from gestao.viagens.modelos_do_sistema import semear
from gestao.viagens.models import FuncaoOS, ModeloOS

from .conftest import entrar, rodar_axe

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 1440])
def test_gestor_cria_modelo_com_funcoes(pagina, dados_e2e, largura):
    pg = pagina
    semear(ModeloOS, FuncaoOS)  # o banco transacional do E2E pode ter sido limpo
    pg.set_viewport_size({"width": largura, "height": 900})
    entrar(pg, "gestor")
    pg.goto("/viagens/ordens/modelos/")
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Modelos de ordem de serviço")
    # Os modelos do sistema já estão na lista.
    expect(pg.get_by_role("link", name="Caminhão", exact=True)).to_be_visible()
    assert not rodar_axe(pg)
    pg.get_by_role("button", name="Novo modelo").first.click()
    janela = pg.get_by_role("dialog", name="Novo modelo de OS")
    janela.get_by_role("textbox", name="Nome", exact=True).fill("Operação com foto")
    janela.get_by_role("textbox", name="Referência (Ref.:)").fill(
        "Deslocamento de Operação Policial")
    janela.get_by_role("textbox", name="Ida (dia da saída)").fill(
        "O deslocamento {equipe} para {municipio} {data}.")
    janela.get_by_role("textbox", name="Dias do evento", exact=True).fill(
        "Que o policial {servidores} acompanhe a operação em {destino} {data}.")
    janela.get_by_role("textbox", name="Volta (dia da chegada)").fill(
        "Que a equipe retorne a {sede} {data}.")
    for n, nome, texto in ((1, "Motorista", "Que {servidores} conduza o veículo oficial."),
                           (2, "Fotógrafo", "Que {servidores} registre a operação em fotografia.")):
        grupo = janela.get_by_role("group", name=f"Função {n}")
        grupo.get_by_role("textbox", name=f"Função {n}").fill(nome)
        grupo.get_by_role("textbox", name="Atribuição").fill(texto)
    assert not rodar_axe(pg)
    janela.get_by_role("button", name="Criar modelo").click()
    expect(pg.locator(".toast")).to_contain_text("criado")
    expect(pg.get_by_role("link", name="Operação com foto")).to_be_visible()
    modelo = ModeloOS.objects.get(nome="Operação com foto")
    assert [f.codigo for f in modelo.funcoes.all()] == ["motorista", "fotografo"]
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0
