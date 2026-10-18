"""Configuração: salvar, erro, substituição e consulta em todas as larguras."""
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gestao.cadastros.models import Lotacao, Servidor, Unidade

from .conftest import entrar
from .test_justificativas_identidade import _axe_estavel

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_configuracao_salvar_substituir_e_consultar(pagina, largura):
    pg = pagina
    Servidor.objects.create(nome="Substituto de teste visual")
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.get_by_role("button", name="Menu do usuário", exact=False).click()
    itens = pg.locator(".cabecalho .menu__painel [role=menuitem]")
    expect(itens.nth(0)).to_contain_text("Alterar senha")
    expect(itens.nth(1)).to_contain_text("Dados da unidade")
    pg.get_by_role("menuitem", name="Dados da unidade", exact=False).click()
    expect(pg.get_by_role("heading", name="Dados da unidade", exact=True)).to_be_visible()
    expect(pg.get_by_text("Unidade em administração:", exact=False)).to_be_visible()
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    nome = pg.locator("#id_nome_extenso")
    expect(nome).to_be_enabled()
    nome.fill("")
    pg.get_by_role("button", name="Salvar dados da unidade", exact=True).click()
    expect(pg.locator("#id_nome_extenso-erro")).to_be_visible()
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"erro-{largura}.png"), full_page=True)
    nome.fill("Unidade sintética de conferência visual")
    pg.get_by_role("button", name="Salvar dados da unidade", exact=True).click()
    expect(pg.locator(".toast")).to_contain_text("salvos")
    expect(nome).to_have_value("Unidade sintética de conferência visual")
    abrir = pg.get_by_role("button", name="Nova substituição", exact=True)
    abrir.focus()
    abrir.press("Enter")
    dialog = pg.get_by_role("dialog", name="Nova substituição")
    expect(dialog).to_be_visible()
    dialog.locator("#id_servidor-busca").fill("Substituto de teste visual")
    dialog.get_by_role("option", name="Substituto de teste visual", exact=True).click()
    calendario = dialog.locator("pc-data[data-periodo] .mesa-evento__botao")
    calendario.click()
    foco = date.fromisoformat(dialog.locator(".calendario td[tabindex='0']").get_attribute("data-data"))
    mes = foco.strftime("%Y-%m")
    dialog.locator(f".calendario td[data-data='{mes}-10']").click()
    dialog.locator(f".calendario td[data-data='{mes}-15']").click()
    inicio = dialog.locator("[data-periodo-de]")
    inicio_texto = f"10/{foco:%m/%Y}"
    expect(inicio).to_have_value(inicio_texto)
    assert dialog.locator(".mesa-evento").evaluate("e=>e.clientWidth") >= 230
    dialog.get_by_label("Motivo", exact=True).fill("Afastamento sintético para teste")
    _axe_estavel(pg)
    dialog.screenshot(path=str(out/f"substituicao-{largura}.png"))
    pg.keyboard.press("Escape")
    expect(abrir).to_be_focused()
    abrir.press("Enter")
    expect(inicio).to_have_value(inicio_texto)
    # Reabertura foca a busca: fechar a lista antes de alcançar a ação do diálogo.
    pg.keyboard.press("Tab")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Cadastrar substituição", exact=True).click()
    registro = pg.locator('section[aria-labelledby="t-substituicoes"] .registro').filter(has_text="Substituto de teste visual")
    expect(registro).to_be_visible()
    registro.get_by_role("button", name="Encerrar", exact=True).click()
    expect(registro.get_by_role("button", name="Reativar", exact=True)).to_be_visible()
    registro.get_by_role("button", name="Reativar", exact=True).click()
    expect(registro.get_by_role("button", name="Encerrar", exact=True)).to_be_visible()
    _axe_estavel(pg)
    pg.context.clear_cookies()
    entrar(pg, "operador")
    pg.goto("/cadastros/configuracao/")
    expect(pg.locator("#id_nome_extenso")).to_be_disabled()
    for campo in ("assina_oficio", "assina_justificativa", "assina_plano", "coordenador_plano"):
        expect(pg.locator(f"#id_{campo}-busca")).to_be_disabled()
    expect(pg.get_by_role("button", name="Salvar dados da unidade", exact=True)).to_have_count(0)
    expect(pg.get_by_role("button", name="Nova substituição", exact=True)).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"consulta-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_configuracao_ausente_e_usuario_sem_unidade(pagina, dados_e2e, largura):
    nova = Unidade.objects.create(nome="Unidade sintética sem configuração", sigla="NOVA")
    Lotacao.objects.filter(usuario=dados_e2e.usuarios["gestor"]).update(unidade=nova)
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto("/cadastros/configuracao/")
    expect(pg.get_by_text("NOVA ainda não tem configuração", exact=False)).to_be_visible()
    expect(pg.get_by_role("button", name="Nova substituição", exact=True)).to_have_count(0)
    _axe_estavel(pg)
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out/f"sem-configuracao-{largura}.png"), full_page=True)
    Lotacao.objects.filter(usuario=dados_e2e.usuarios["operador"]).delete()
    pg.context.clear_cookies()
    entrar(pg, "operador")
    pg.goto("/cadastros/configuracao/")
    expect(pg.get_by_role("heading", name="Sem unidade", exact=True)).to_be_visible()
    expect(pg.locator("#form-configuracao")).to_have_count(0)
    _axe_estavel(pg)
    pg.screenshot(path=str(out/f"sem-unidade-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")


@pytest.mark.parametrize("largura", [360, 1440])
def test_dados_unidade_troca_contexto_e_persiste_assinante(pagina, largura):
    import re

    from gestao.cadastros.models import ConfiguracaoInstitucional

    dpc = Unidade.objects.get(sigla="DPC")
    assinante = Servidor.objects.create(
        nome="Assinante sintético de nome extenso para conferência da unidade", unidade=dpc)
    outro = Servidor.objects.create(
        nome="Outro assinante sintético com identificação longa para troca de titular", unidade=dpc)
    anterior = ConfiguracaoInstitucional.objects.get(unidade__sigla="ASCOM").nome_extenso
    pg = pagina
    entrar(pg, "gestor")
    pg.set_viewport_size({"width": largura, "height": 800})
    pg.get_by_role("button", name="Menu do usuário", exact=False).click()
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(out / f"menu-unidade-{largura}.png"))
    pg.get_by_role("menuitem", name="Dados da unidade", exact=False).click()
    pg.locator("#escolha-unidade-gatilho").click()
    pg.get_by_role("option", name=re.compile("^DPC")).click()
    pg.get_by_role("button", name="Abrir", exact=True).click()
    expect(pg.get_by_text("Unidade em administração:", exact=False)).to_contain_text("DPC")
    expect(pg.locator("#form-configuracao input[name=unidade]")).to_have_value(str(dpc.pk))
    pg.locator("#id_nome_extenso").fill("Divisão sintética: alteração no contexto DPC")
    pg.locator("#id_assina_oficio-busca").fill("Assinante sintético")
    pg.get_by_role("option", name=re.compile("^Assinante sintético")).click()
    pg.get_by_role("button", name="Salvar dados da unidade", exact=True).click()
    pg.reload()
    expect(pg.locator("#id_nome_extenso")).to_have_value(
        "Divisão sintética: alteração no contexto DPC")
    expect(pg.locator("#id_assina_oficio")).to_have_value(str(assinante.pk))
    busca = pg.locator("#id_assina_oficio-busca")
    busca.fill("Outro assinante sintético")
    expect(busca).to_have_value("Outro assinante sintético")
    expect(pg.locator("#id_assina_oficio")).to_have_value("")
    pg.get_by_role("option", name=re.compile("^Outro assinante sintético")).click()
    pg.get_by_role("button", name="Salvar dados da unidade", exact=True).click()
    pg.reload()
    expect(pg.locator("#id_assina_oficio")).to_have_value(str(outro.pk))
    assert ConfiguracaoInstitucional.objects.get(unidade__sigla="ASCOM").nome_extenso == anterior
    _axe_estavel(pg)
    pg.screenshot(path=str(out / f"dados-unidade-{largura}.png"), full_page=True)
    assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")


@pytest.mark.visual
def test_evidencias_estaveis_menu_e_secoes_da_unidade(pagina):
    from gestao.cadastros.models import ConfiguracaoInstitucional

    pg = pagina
    pg.emulate_media(reduced_motion="reduce")
    unidade = Unidade.objects.get(sigla="DPC")
    servidor = Servidor.objects.create(
        nome="Outro assinante sintético com identificação longa para troca de titular",
        unidade=unidade)
    ConfiguracaoInstitucional.objects.filter(unidade=unidade).update(
        nome_extenso="Divisão sintética: alteração no contexto DPC", assina_oficio=servidor)
    entrar(pg, "gestor")
    out = Path("artifacts/configuracao")
    out.mkdir(parents=True, exist_ok=True)
    for largura in (360, 1440):
        pg.set_viewport_size({"width": largura, "height": 900})
        pg.goto(f"/cadastros/configuracao/?unidade={unidade.pk}")
        _axe_estavel(pg)
        pg.get_by_role("button", name="Menu do usuário", exact=False).click()
        painel = pg.locator(".cabecalho .menu__painel")
        expect(painel).to_be_visible()
        painel.evaluate("async e => await Promise.all(e.getAnimations({subtree:true}).map(a => a.finished.catch(() => {})))")
        pg.screenshot(path=str(out / f"menu-unidade-{largura}.png"), animations="disabled")
        pg.keyboard.press("Escape")
        pg.locator("#t-instituicao").evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 150)")
        pg.screenshot(path=str(out / f"identificacao-unidade-{largura}.png"), animations="disabled")
        pg.locator("#id_telefone").evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 150)")
        pg.screenshot(path=str(out / f"contatos-unidade-{largura}.png"), animations="disabled")
        pg.locator("#t-assinaturas").evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 150)")
        pg.screenshot(path=str(out / f"assinantes-unidade-{largura}.png"), animations="disabled")
        assert not pg.evaluate("document.documentElement.scrollWidth>innerWidth")



def test_operador_consulta_assinantes_com_buscas_desabilitadas(pagina):
    pg = pagina
    pg.emulate_media(reduced_motion="reduce")
    entrar(pg, "operador")
    for largura in (360, 1440):
        pg.set_viewport_size({"width": largura, "height": 900})
        pg.goto("/cadastros/configuracao/")
        expect(pg.locator("#id_nome_extenso")).to_be_disabled()
        for campo in ("assina_oficio", "assina_justificativa", "assina_plano", "coordenador_plano"):
            expect(pg.locator(f"#id_{campo}-busca")).to_be_disabled()
        expect(pg.get_by_role("button", name="Salvar dados da unidade", exact=True)).to_have_count(0)
        expect(pg.get_by_role("button", name="Nova substituição", exact=True)).to_have_count(0)
        _axe_estavel(pg)
