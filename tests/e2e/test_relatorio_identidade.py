"""Relato legível e "Salvar e continuar" que preserva a gravação pendente."""

import re

import pytest
from playwright.sync_api import expect

from gestao.viagens.models import PrestacaoContas, RelatorioTecnico

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_relato_continuar_e_valores_individuais(logado, dados_e2e, largura):
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 600})
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/relatorio/")
    expect(pg.get_by_role("heading", level=1)).to_have_count(1)
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Relatório técnico")
    linha = pg.locator("#diarias .registro-valor").first
    valor = linha.get_by_label(re.compile("Valor recebido"))
    expect(valor).to_be_visible()
    expect(valor).to_have_accessible_description(re.compile("Liberada"))
    expect(linha.locator(".registro-valor__identidade")).to_contain_text("Liberada")
    assert pg.locator(".barra-acoes").evaluate("e=>getComputedStyle(e).position") == "sticky"  # rodapé grudado, como no ofício
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")
    expect(pg.locator("[data-status-salvamento]")).to_be_visible()
    texto = "Relato salvo antes de sair pelo teclado."
    pg.get_by_label("Objetivo da participação").fill(texto)
    # Não aguarda o anúncio de autosave: continuar precisa coordenar a gravação.
    pg.get_by_role("button", name="Salvar e continuar").last.focus()
    pg.keyboard.press("Enter")
    expect(pg).to_have_url(re.compile(rf"/viagens/prestacoes/equipe/{p.pk}/leitura/\?servidor=\d+$"))
    assert RelatorioTecnico.objects.get(prestacao=p).atividade == texto
    assert not p.servidores.filter(finalizada_em__isnull=False).exists()
    assert pg.erros_console == []


def test_texto_pronto_compartilhado_e_dialogo_preservam_relato(logado, dados_e2e):
    from gestao.cadastros.models import ModeloTexto

    ModeloTexto.objects.create(tipo="rt_conclusao", nome="Conclusão conferida",
                               texto="Atendimento concluído pela equipe.")
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    pg = logado
    pg.set_viewport_size({"width": 360, "height": 700})
    pg.goto(f"/viagens/prestacoes/equipe/{p.pk}/relatorio/")
    campo = pg.locator("#rt-conclusao")
    campo.fill("")
    pg.get_by_role("combobox", name="Texto pronto para Conclusão").click()
    pg.get_by_role("option", name="Conclusão conferida").click()
    expect(campo).to_have_value("Atendimento concluído pela equipe.")
    bloco = pg.locator('[data-texto-pronto][data-alvo="rt-conclusao"]')
    guardar = bloco.get_by_role("button", name="Guardar texto", exact=True)
    guardar.click()
    dialogo = pg.get_by_role("dialog", name="Guardar como texto pronto")
    expect(dialogo).to_be_visible()
    expect(dialogo.get_by_role("textbox", name="Nome", exact=True)).to_be_focused()
    pg.keyboard.press("Escape")
    expect(dialogo).not_to_be_visible()
    expect(guardar).to_be_focused()
    expect(campo).to_have_value("Atendimento concluído pela equipe.")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Salvo automaticamente")
    assert RelatorioTecnico.objects.get(prestacao=p).conclusao == "Atendimento concluído pela equipe."
