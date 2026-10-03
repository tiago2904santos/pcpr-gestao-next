"""E2E: jornada completa do operador e verificações de teclado/permissão.

Roda no Chromium real contra o live_server com PostgreSQL. O worker da outbox é
acionado pelo próprio teste (em produção é um processo separado).
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gestao.plataforma import outbox
from gestao.viagens.models import Documento, Oficio

from .conftest import entrar

pytestmark = pytest.mark.e2e


def _data_hora(pg, campo: str, dias: int, hora: int, minuto: int = 0) -> None:
    """Data e hora em campos separados (dd/mm/aaaa e hh:mm), como a pessoa digita."""
    alvo = timezone.localtime() + timedelta(days=dias)
    pg.locator(f"#id_{campo}_0").fill(alvo.strftime("%d/%m/%Y"))
    pg.locator(f"#id_{campo}_1").fill(f"{hora:02d}:{minuto:02d}")


def test_operador_cria_preenche_e_emite_um_oficio(logado):
    pg = logado
    pg.goto("/viagens/oficios/")
    # Como no sistema de referência: o botão já cria o ofício e abre a folha completa.
    pg.get_by_role("button", name="Novo ofício").first.click()
    expect(pg.locator(".toast")).to_contain_text("criado")
    titulo = pg.get_by_role("heading", level=1).inner_text()
    numero = re.search(r"\d{2,}/\d{4}", titulo).group(0)  # D2: "05/2026"
    pg.get_by_label("Motivo da viagem").fill("Cobertura do evento PCPR na Comunidade.")

    # Equipe via combobox remoto (HTMX, salva na hora).
    busca = pg.get_by_role("combobox", name="Adicionar servidor")
    busca.fill("isab")
    pg.get_by_role("option", name=re.compile("Isabela Prado")).click()
    expect(pg.locator("#equipe")).to_contain_text("Isabela Prado Cavalcanti")
    pg.get_by_role("button", name="Marcar Isabela Prado Cavalcanti como motorista").click()
    expect(pg.locator("#equipe .selo--forte")).to_contain_text("Motorista")

    # Protocolo (obrigatório para emitir — D1), transporte e roteiro (formulário principal).
    pg.get_by_label("Protocolo", exact=False).fill("123456789")
    pg.locator("#id_viatura-busca").fill("ABC")
    pg.get_by_role("option", name=re.compile("ABC1D23")).click()
    pg.locator("input[name='destino-0-cidade']").fill("Londrina/PR")
    # Itinerário 2.0: só a saída; tempo de estrada e adicional vêm da rota, a chegada é
    # calculada na tela (e de novo no servidor).
    _data_hora(pg, "destino-0-saida", 15, 8)
    _data_hora(pg, "retorno-saida", 17, 8)
    expect(pg.locator("#id_destino-0-tempo_viagem")).not_to_have_value("")
    expect(pg.locator("[data-total-km]")).to_contain_text("km")
    pg.get_by_role("button", name="Salvar rascunho").click()

    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")
    expect(pg.locator("#equipe .selo--forte")).to_contain_text("Motorista")
    diarias = pg.locator("#diarias")
    expect(diarias).to_contain_text("2 x 100% + 1 x 15%")
    expect(diarias).to_contain_text("R$ 624,68")
    expect(pg.locator("#justificativa .selo")).to_have_text("Dispensada")

    pg.get_by_role("button", name="Revisar e emitir").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Revisar e emitir")
    pg.get_by_role("button", name="Emitir ofício").click()
    dialogo = pg.get_by_role("dialog", name="Emitir ofício?")
    expect(dialogo).to_be_visible()
    dialogo.get_by_role("button", name="Emitir").click()

    expect(pg.locator(".toast")).to_contain_text(f"Ofício {numero} emitido")
    expect(pg.locator(".pagina-cabecalho .processo__passo--atual")).to_have_text("Emitido")
    expect(pg.locator("#documentos-lista")).to_contain_text("Gerando")

    while outbox.processar_lote():
        pass
    # A lista se atualiza sozinha (HTMX a cada 2s) quando o PDF fica pronto.
    expect(pg.locator("#documentos-lista")).to_contain_text("PDF/A pronto", timeout=8000)
    n, ano = numero.split("/")
    oficio = Oficio.objects.get(numero=int(n), ano=int(ano))
    assert oficio.documentos.get(tipo=Documento.Tipo.OFICIO).situacao == "pronto"
    assert pg.erros_console == []


def test_emissao_bloqueada_sem_justificativa_mostra_o_motivo(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    expect(pg.locator("#justificativa .selo")).to_have_text("Obrigatória")
    expect(pg.locator(".barra-acoes__status")).to_contain_text("pendência")
    pg.get_by_role("button", name="Revisar e emitir").click()
    # Com pendências, salva e volta para a seção de emissão (sem beco sem saída).
    expect(pg.locator(".toast")).to_contain_text("pendência")
    expect(pg).to_have_url(re.compile(r"/editar/#emissao$"))
    expect(pg.locator("#emissao .checklist")).to_contain_text("Justificativa obrigatória")
    # Mesmo pela URL direta, a revisão não deixa emitir.
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/emitir/")
    expect(pg.get_by_role("button", name="Emitir ofício")).to_be_disabled()


def test_enter_salva_e_alteracao_nao_salva_e_avisada(logado, dados_e2e):
    pg = logado
    url = f"/viagens/oficios/{dados_e2e.ids['oficio_vazio']}/editar/"
    pg.goto(url)
    status = pg.locator("[data-status-salvamento]")
    protocolo = pg.get_by_label("Protocolo", exact=False)
    protocolo.fill("123456789")
    expect(status).to_contain_text("não salvas")

    # Sair com alterações pendentes pede confirmação (beforeunload).
    avisos: list[str] = []
    pg.once("dialog", lambda d: (avisos.append(d.type), d.dismiss()))
    pg.get_by_role("link", name="Ofícios").first.click()
    assert avisos == ["beforeunload"]
    expect(pg).to_have_url(re.compile(re.escape(url)))

    # Enter num campo de texto salva o rascunho (não adiciona destino nem emite).
    protocolo.press("Enter")
    expect(status).to_contain_text("Rascunho salvo às")
    expect(pg.get_by_label("Protocolo", exact=False)).to_have_value(re.compile(r"^12\D?345\D?678\D?9$"))
    expect(status).not_to_contain_text("não salvas")


def test_erro_de_validacao_aparece_no_resumo_e_no_campo(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_vazio']}/editar/")
    pg.get_by_label("Protocolo", exact=False).fill("123")
    pg.get_by_role("button", name="Salvar rascunho").click()
    resumo = pg.locator("#resumo-erros")
    expect(resumo).to_contain_text("O protocolo tem 9 dígitos")
    expect(resumo).to_be_focused()  # leitor de tela anuncia os erros logo após salvar
    campo = pg.get_by_label("Protocolo", exact=False)
    expect(campo).to_have_attribute("aria-invalid", "true")
    resumo.get_by_role("link").first.click()
    expect(campo).to_be_focused()


def test_teclado_pular_conteudo_menu_e_dialogo(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_emitido']}/")
    pg.keyboard.press("Tab")
    expect(pg.get_by_role("link", name="Pular para o conteúdo")).to_be_focused()
    pg.keyboard.press("Enter")
    expect(pg.locator("main#conteudo")).to_be_focused()

    menu = pg.get_by_role("button", name="Menu do usuário Operador de Testes")
    menu.focus()
    pg.keyboard.press("ArrowDown")
    expect(pg.get_by_role("menuitem", name="Alterar senha")).to_be_focused()
    pg.keyboard.press("Escape")
    expect(menu).to_be_focused()

    pg.keyboard.press("Control+k")
    paleta = pg.get_by_role("dialog", name="Buscar ou ir para")
    expect(paleta).to_be_visible()
    pg.keyboard.type("01/")
    expect(paleta.get_by_role("option").first).to_contain_text("Ofício 01/")
    pg.keyboard.press("Escape")
    expect(paleta).to_be_hidden()


def test_consulta_ve_mas_nao_cria_nem_edita(pagina, dados_e2e):
    entrar(pagina, "consulta")
    pagina.goto("/viagens/oficios/")
    expect(pagina.get_by_role("button", name="Novo ofício")).to_have_count(0)
    resposta = pagina.goto("/viagens/oficios/novo/")
    assert resposta.status == 403
    expect(pagina.get_by_role("heading", level=1)).to_have_text("Acesso não permitido")


def test_operador_nao_ve_oficio_de_outra_unidade(logado, dados_e2e):
    resposta = logado.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_outra_unidade']}/")
    assert resposta.status == 404
    expect(logado.get_by_role("heading", level=1)).to_have_text("Página não encontrada")


def test_gaveta_de_navegacao_no_celular(logado):
    pg = logado
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto("/viagens/oficios/")
    nav = pg.get_by_role("navigation", name="Navegação principal")
    expect(nav).not_to_be_in_viewport()
    botao = pg.get_by_role("button", name="Abrir menu de navegação")
    botao.click()
    expect(nav).to_be_in_viewport()
    expect(botao).to_have_attribute("aria-expanded", "true")
    pg.keyboard.press("Escape")
    expect(botao).to_be_focused()
    expect(botao).to_have_attribute("aria-expanded", "false")


def test_menu_superior_com_item_ativo_e_submenu_por_teclado(logado):
    pg = logado
    pg.goto("/viagens/oficios/")
    nav = pg.get_by_role("navigation", name="Navegação principal")
    expect(nav).to_be_in_viewport()
    expect(nav.get_by_role("link", name="Ofícios")).to_have_attribute("aria-current", "page")
    cadastros = nav.get_by_role("button", name="Cadastros")
    cadastros.focus()
    pg.keyboard.press("Enter")
    expect(nav.get_by_role("menuitem", name="Servidores")).to_be_focused()
    pg.keyboard.press("ArrowDown")
    expect(nav.get_by_role("menuitem", name="Viaturas")).to_be_focused()
    pg.keyboard.press("Escape")
    expect(cadastros).to_be_focused()
    cadastros.click()
    nav.get_by_role("menuitem", name="Servidores").click()
    expect(pg).to_have_url(re.compile("/cadastros/servidores/"))
    expect(pg.get_by_role("button", name=re.compile("Cadastros.*seção atual"))).to_be_visible()


def test_seletor_de_modulo_leva_a_central(logado):
    pg = logado
    pg.goto("/viagens/")
    pg.get_by_role("button", name="Módulo atual: Viagens. Trocar de módulo").click()
    pg.get_by_role("menuitem", name="Central de módulos").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Central de módulos")


def test_sistema_nao_muda_com_sistema_operacional_em_modo_escuro(navegador, live_server, dados_e2e):
    """Sem modo escuro: com o SO/navegador em dark, o sistema continua claro."""
    contexto = navegador.new_context(color_scheme="dark", base_url=live_server.url,
                                     viewport={"width": 1280, "height": 900})
    pg = contexto.new_page()
    entrar(pg)
    pg.goto("/viagens/oficios/")
    fundo = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    esquema = pg.evaluate("getComputedStyle(document.documentElement).colorScheme")
    contexto.close()
    assert fundo == "rgb(246, 245, 242)"  # --neutro-50
    assert esquema == "light"


def test_ctrl_s_salva_o_rascunho(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_vazio']}/editar/")
    pg.get_by_label("Motivo da viagem").fill("Apoio ao evento regional.")
    pg.keyboard.press("Control+s")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")
    expect(pg.get_by_label("Motivo da viagem")).to_have_value("Apoio ao evento regional.")


@pytest.mark.parametrize("largura", [360, 768, 1440])
def test_campo_focado_nunca_fica_atras_do_topo_ou_da_barra(logado, dados_e2e, largura):
    """WCAG 2.4.11: com Tab, o foco não some sob o topo, a faixa de progresso fixa ou a barra."""
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 700})
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    pg.get_by_role("textbox", name="Data do ofício", exact=True).focus()
    escondidos = []
    for _ in range(25):
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(30)
        r = pg.evaluate("""() => {
          const el = document.activeElement;
          if (!el || el.closest('.barra-acoes, .topo')) return null;
          const c = el.getBoundingClientRect();
          const faixa = document.querySelector('.progresso--fixo');
          const topo = Math.max(document.querySelector('.topo').getBoundingClientRect().bottom,
                                faixa ? faixa.getBoundingClientRect().bottom : 0);
          const barra = document.querySelector('.barra-acoes').getBoundingClientRect().top;
          return {id: el.id || el.name || el.tagName, c: c.top, b: c.bottom, topo, barra};
        }""")
        if r and (r["c"] < r["topo"] - 1 or r["b"] > r["barra"] + 1):
            escondidos.append(r)
    assert escondidos == [], escondidos


def test_registro_da_lista_abre_resumo_em_janela_e_fecha_com_esc(logado, dados_e2e):
    """Clicar no registro mostra roteiro/equipe/documentos numa janela, sem sair da lista."""
    pg = logado
    pg.goto("/viagens/oficios/")
    janela = pg.locator("#dialogo-resumo")
    expect(janela).to_be_hidden()
    pg.locator(".registro__link").first.click()
    expect(janela).to_be_visible()
    expect(janela.locator(".resumo")).to_contain_text("Roteiro")
    expect(janela.locator(".resumo")).to_contain_text("Equipe")
    expect(janela.get_by_role("link", name="Ver o ofício inteiro")).to_be_visible()
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    assert pg.url.endswith("/viagens/oficios/")  # a lista continua onde estava


def test_gaveta_de_filtros_filtra_por_protocolo(logado, dados_e2e):
    """Os filtros finos ficam guardados; abertos, valem na hora e aparecem na URL."""
    pg = logado
    pg.goto("/viagens/oficios/")
    gaveta = pg.locator("#filtros-mais")
    expect(gaveta.locator(".filtros__avancados")).to_be_hidden()
    gaveta.get_by_text("Mais filtros").click()
    gaveta.get_by_label("Protocolo").fill("123456789")
    expect(pg.locator(".lista-cabecalho__total")).to_contain_text("1 ofício")
    assert "protocolo=123456789" in pg.url


def test_lista_agrupa_por_mes_e_nomeia_transicoes(logado, dados_e2e):
    pg = logado
    pg.goto("/viagens/oficios/")
    expect(pg.locator(".registros__grupo").first).to_be_visible()
    assert pg.locator(".registro .placa[data-vt]").count() == pg.locator(".registro").count()
    # a placa da lista e a placa do detalhe compartilham o nome (continuidade espacial)
    nome = pg.locator(".registro .placa").first.get_attribute("data-vt")
    pg.locator(".registro__link").first.click()
    expect(pg.locator(".pagina-cabecalho__placa")).to_have_attribute("data-vt", nome)


def test_formulario_do_oficio_cartoes_de_escolha_itinerario_e_conferencia(logado, dados_e2e):
    """Cadastro do ofício: escolhas como cartões (rádios nativos), campo condicional colado à
    escolha, roteiro como itinerário sede → destinos → sede e conferência no fim."""
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    # Custeio: "Outra instituição" revela o campo da instituição (sem JS: :has()).
    instituicao = pg.get_by_label("Instituição que custeia")
    pg.locator("label.opcao").filter(has_text="Diárias e combustível pela unidade").click()
    expect(instituicao).to_be_hidden()
    pg.locator("label.opcao").filter(has_text="Outra instituição").click()
    expect(pg.get_by_role("radio", name=re.compile("^Outra instituição"))).to_be_checked()
    expect(instituicao).to_be_visible()
    # Teclado: setas trocam o meio de transporte (rádios nativos sob os cartões).
    pg.locator("label.opcao").filter(has_text="Viatura oficial").click()
    viatura = pg.get_by_role("radio", name=re.compile("^Viatura oficial"))
    expect(viatura).to_be_checked()
    viatura.focus()
    pg.keyboard.press("ArrowDown")
    expect(pg.get_by_role("radio", name=re.compile("^Outro meio"))).to_be_checked()
    expect(pg.get_by_label("Descrição do transporte")).to_be_visible()
    # Porte de arma é um interruptor.
    expect(pg.get_by_role("switch", name=re.compile(r"^Porte.tr.nsito de arma"))).to_be_visible()
    # Itinerário: começa e termina na sede; o trecho diz de onde sai.
    expect(pg.locator("#roteiro .itin__parada--sede")).to_contain_text("Sede (origem da viagem)")
    expect(pg.locator("#roteiro .itin__trecho").last).to_contain_text("Chegada na sede")
    expect(pg.locator("#roteiro .itin__trecho-rota").first).to_contain_text("Curitiba/PR")
    # Documentos: diz quantas pendências faltam e lista os cartões (Identificação, Roteiro
    # e, aqui, Justificativa — este ofício está fora do prazo).
    expect(pg.locator("#emissao .conferencia__titulo")).to_contain_text("para emitir")
    itens = pg.locator("#emissao .conferencia__item")
    expect(itens).to_have_count(3)
    expect(itens.first).to_contain_text("Identificação")


def test_clique_em_texto_nao_rola_a_pagina_nem_perde_a_escolha(logado, dados_e2e):
    """Regressão: com tabindex fixo no <main>, apertar o mouse num texto não focável dava
    foco ao <main>, a página rolava antes de soltar o botão e o clique no cartão se perdia."""
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    descricao = pg.locator("label.opcao").filter(has_text="Outro meio").locator(".opcao__descricao")
    descricao.scroll_into_view_if_needed()
    antes = pg.evaluate("scrollY")
    descricao.click()
    expect(pg.get_by_role("radio", name=re.compile("^Outro meio"))).to_be_checked()
    assert pg.evaluate("scrollY") == antes
    expect(pg.locator("main#conteudo")).not_to_have_attribute("tabindex", "-1")


def test_faixa_de_progresso_fica_fixa_e_marca_a_secao_atual(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    faixa = pg.locator(".progresso--fixo")
    pg.locator("#roteiro").scroll_into_view_if_needed()
    pg.mouse.wheel(0, 200)
    expect(faixa).to_be_in_viewport()
    expect(faixa).to_have_class(re.compile("progresso--flutuando"))
    expect(faixa.locator("[aria-current='location']")).to_have_count(1)


def test_novo_oficio_cria_e_abre_a_folha_completa(logado):
    """Como no sistema de referência: não há página "novo"; o botão cria o ofício."""
    pg = logado
    pg.goto("/viagens/")
    pg.get_by_role("button", name="Novo ofício").first.click()
    expect(pg).to_have_url(re.compile(r"/viagens/oficios/\d+/editar/$"))
    expect(pg.get_by_role("heading", level=1)).to_contain_text("Ofício ")
    # Quatro cartões; dentro de Identificação cada assunto guarda a própria âncora.
    for ancora in ("identificacao", "dados", "equipe", "transporte", "diarias",
                   "roteiro", "emissao"):
        expect(pg.locator(f"#{ancora}")).to_be_attached()
    # Rascunho recém-criado não tem saída marcada: sem prazo a cumprir, o cartão da
    # justificativa nem aparece.
    expect(pg.locator("#justificativa")).to_have_count(0)
    assert pg.erros_console == []  # type: ignore[attr-defined]


def test_sem_seletores_nativos_de_data_hora_ou_lista(logado, dados_e2e):
    """Calendário, relógio e listas são do design system, nunca os do navegador."""
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    nativos = pg.locator("input[type=date], input[type=time], input[type=datetime-local]")
    expect(nativos).to_have_count(0)
    expect(pg.locator("select:visible")).to_have_count(0)
    expect(pg.locator("pc-data .seletor__botao:visible").first).to_be_visible()


def test_calendario_por_teclado(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    campo = pg.get_by_role("textbox", name="Data do ofício", exact=True)
    campo.fill("08/10/2026")
    botao = pg.get_by_role("button", name="Escolher data: Data do ofício")
    botao.click()
    calendario = pg.get_by_role("dialog", name="Escolher data: Data do ofício")
    expect(calendario).to_be_visible()
    expect(calendario.get_by_role("grid")).to_have_accessible_name("Outubro de 2026")
    expect(pg.locator("td[aria-selected='true']")).to_have_text("8")
    expect(pg.locator(":focus")).to_have_text("8")  # o foco começa no dia escolhido
    pg.keyboard.press("ArrowRight")
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("Enter")
    expect(campo).to_have_value("16/10/2026")
    expect(calendario).to_be_hidden()
    expect(botao).to_be_focused()
    botao.click()
    pg.keyboard.press("PageDown")
    expect(calendario.get_by_role("grid")).to_have_accessible_name("Novembro de 2026")
    pg.keyboard.press("Escape")
    expect(calendario).to_be_hidden()
    expect(campo).to_have_value("16/10/2026")  # Esc não muda nada
    expect(botao).to_be_focused()


def test_relogio_e_lista_propria(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    hora = pg.locator("#id_destino-0-saida_1")
    hora.fill("09:00")
    pg.get_by_role("button", name=re.compile(r"^Escolher hora: Saída")).first.click()
    horas = pg.get_by_role("listbox", name="Horas")
    expect(horas).to_be_focused()
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("ArrowRight")
    expect(pg.get_by_role("listbox", name="Minutos")).to_be_focused()
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("ArrowDown")
    pg.keyboard.press("Enter")
    expect(hora).to_have_value("10:10")
    # Máscara: digitar só números monta a data.
    data = pg.locator("#id_destino-0-saida_0")
    data.fill("")
    data.press_sequentially("21102026")
    expect(data).to_have_value("21/10/2026")
    # Lista própria (combustível): abre, navega e escolhe; o <select> oculto acompanha.
    pg.locator("label.opcao").filter(has_text="Outro meio").click()
    lista = pg.get_by_role("combobox", name=re.compile("^Combustível"))
    lista.click()
    expect(lista).to_have_attribute("aria-expanded", "true")
    pg.get_by_role("option", name="Diesel").click()
    expect(lista).to_contain_text("Diesel")
    expect(pg.locator("#id_transporte_combustivel")).to_have_value(re.compile(r"\d+"))
    lista.press("ArrowDown")
    pg.keyboard.press("Escape")
    expect(lista).to_have_attribute("aria-expanded", "false")
    assert pg.erros_console == []  # type: ignore[attr-defined]
