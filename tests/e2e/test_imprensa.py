"""E2E: atendimento à imprensa — registrar o pedido, a folha se grava sozinha, o andamento
muda a situação e vai para o histórico, a lista filtra pela fila e o painel conta."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _dar_papel(login: str = "operador", papel: str = "ASCOM_IMPRENSA") -> None:
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    Usuario.objects.get(login=login).groups.add(Group.objects.get(name=papel))


def test_registrar_gravar_sozinho_e_andamento(logado, dados_e2e):
    from gestao.imprensa.models import Atendimento, Veiculo

    _dar_papel()
    Veiculo.objects.create(nome="RPC")
    pg = logado
    pg.goto("/imprensa/")
    pg.get_by_role("link", name="Novo atendimento").first.click()
    pg.get_by_label("Jornalista").fill("Ana Paula (e2e)")
    pg.get_by_label("Outro veículo (não listado)").fill("Rádio Clube")
    pg.locator("#id_pedido").fill("Dados da operação de ontem (e2e)")
    pg.get_by_role("button", name="Registrar atendimento").click()
    expect(pg).to_have_url(re.compile(r"/imprensa/atendimentos/\d+/$"))
    a = Atendimento.objects.get()
    assert a.veiculo and a.veiculo.nome == "Rádio Clube"
    expect(pg.locator("#frase-atendimento")).to_contain_text("Em andamento")

    pg.get_by_role("textbox", name="Resposta enviada").fill("Nota enviada (e2e)")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text(re.compile("Salvo"),
                                                                    timeout=10000)
    a.refresh_from_db()
    assert a.resposta == "Nota enviada (e2e)"

    pg.locator("label.opcao", has_text="Atendido").click()
    pg.locator("#id_anotacao").fill("Respondido por telefone (e2e)")
    pg.get_by_role("button", name="Registrar andamento").last.click()
    expect(pg.locator("#frase-atendimento")).to_contain_text("Atendido")
    expect(pg.locator("#historico")).to_contain_text("Respondido por telefone (e2e)")

    pg.goto("/imprensa/atendimentos/?fila=atendidos")
    expect(pg.get_by_role("link", name=re.compile("Ana Paula \\(e2e\\) · Rádio Clube"))
           ).to_be_visible()
    pg.goto("/imprensa/atendimentos/?fila=abertos")
    expect(pg.get_by_text("Nenhum atendimento encontrado")).to_be_visible()
    assert not pg.erros_console  # type: ignore[attr-defined]


def test_sem_papel_nao_ve_o_modulo(logado, dados_e2e):
    pg = logado
    pg.goto("/")
    expect(pg.get_by_role("link", name="Imprensa")).to_have_count(0)
    resposta = pg.goto("/imprensa/")
    assert resposta is not None and resposta.status == 403


@pytest.mark.parametrize("largura", [360, 1440])
def test_telas_sem_rolagem_horizontal(logado, dados_e2e, largura):
    from datetime import timedelta

    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.imprensa import services

    _dar_papel()
    _dar_papel(papel="ADMINISTRADOR")
    u = Usuario.objects.get(login="operador")
    hoje = timezone.localdate()
    a = services.criar(u, {"data": hoje, "jornalista": "Jornalista com nome bem comprido "
                           "para testar a quebra (e2e)", "pedido": "x " * 200,
                           "deadline": hoje + timedelta(days=1),
                           "fonte": "Del. A\n\nIML", "inicio_pedido": "09h\n\n10h"})
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/imprensa/", "/imprensa/atendimentos/", f"/imprensa/atendimentos/{a.pk}/",
                 "/imprensa/atendimentos/novo/", "/imprensa/cadastros/veiculos/"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
