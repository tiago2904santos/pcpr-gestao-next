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


def _dt(dias: int, hora: int, minuto: int = 0) -> str:
    alvo = timezone.localtime() + timedelta(days=dias)
    return alvo.replace(hour=hora, minute=minuto).strftime("%Y-%m-%dT%H:%M")


def test_operador_cria_preenche_e_emite_um_oficio(logado):
    pg = logado
    pg.goto("/viagens/oficios/")
    pg.get_by_role("link", name="Novo ofício").first.click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Novo ofício de viagem")
    pg.get_by_label("Motivo da viagem").fill("Cobertura do evento PCPR na Comunidade.")
    pg.get_by_role("button", name="Criar rascunho e continuar").click()

    expect(pg.locator(".toast")).to_contain_text("criado como rascunho")
    titulo = pg.get_by_role("heading", level=1).inner_text()
    numero = re.search(r"\d{2,}/\d{4}", titulo).group(0)  # D2: "05/2026"

    # Equipe via combobox remoto (HTMX).
    busca = pg.get_by_role("combobox", name="Adicionar servidor")
    busca.fill("isab")
    pg.get_by_role("option", name=re.compile("Isabela Prado")).click()
    expect(pg.locator("#equipe")).to_contain_text("Isabela Prado Cavalcanti")
    pg.get_by_role("button", name="Marcar Isabela Prado Cavalcanti como motorista").click()
    expect(pg.locator("#equipe .selo--forte")).to_contain_text("Motorista")

    # Protocolo (obrigatório para emitir — D1), transporte e roteiro (formulário principal).
    pg.get_by_label("Protocolo (eProtocolo)").fill("123456789")
    pg.locator("#id_viatura-busca").fill("ABC")
    pg.get_by_role("option", name=re.compile("ABC1D23")).click()
    pg.get_by_label("Cidade de destino").fill("Londrina/PR")
    pg.locator("#id_destino-0-saida").fill(_dt(15, 8))
    pg.locator("#id_destino-0-chegada").fill(_dt(15, 14))
    pg.locator("#id_retorno-saida").fill(_dt(17, 8))
    pg.locator("#id_retorno-chegada").fill(_dt(17, 15, 30))
    pg.get_by_role("button", name="Salvar rascunho").click()

    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")
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
    protocolo = pg.get_by_label("Protocolo (eProtocolo)")
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
    expect(pg.get_by_label("Protocolo (eProtocolo)")).to_have_value(re.compile(r"^12\D?345\D?678\D?9$"))
    expect(status).not_to_contain_text("não salvas")


def test_erro_de_validacao_aparece_no_resumo_e_no_campo(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_vazio']}/editar/")
    pg.get_by_label("Protocolo (eProtocolo)").fill("123")
    pg.get_by_role("button", name="Salvar rascunho").click()
    resumo = pg.locator("#resumo-erros")
    expect(resumo).to_contain_text("O protocolo tem 9 dígitos")
    expect(resumo).to_be_focused()  # leitor de tela anuncia os erros logo após salvar
    campo = pg.get_by_label("Protocolo (eProtocolo)")
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
    expect(pagina.get_by_role("link", name="Novo ofício")).to_have_count(0)
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
    pg.get_by_label("Data do ofício").focus()
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


def test_registro_da_lista_expande_com_resumo_e_fecha_com_esc(logado, dados_e2e):
    """Overdrive 2: o registro revela roteiro/equipe/documentos sem sair da lista."""
    pg = logado
    pg.goto("/viagens/oficios/")
    botao = pg.locator("[data-expandir]").first
    registro = pg.locator(".registro").first
    expect(botao).to_have_attribute("aria-expanded", "false")
    botao.click()
    expect(botao).to_have_attribute("aria-expanded", "true")
    expect(registro).to_have_class(re.compile("registro--aberto"))
    expect(registro.locator(".resumo")).to_be_visible()
    expect(registro.locator(".resumo")).to_contain_text("Roteiro")
    pg.keyboard.press("Escape")
    expect(botao).to_have_attribute("aria-expanded", "false")
    expect(registro.locator(".resumo")).to_be_hidden()
    assert pg.evaluate("document.activeElement?.hasAttribute('data-expandir')")


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
    pg.get_by_role("radio", name=re.compile("^Unidade")).check()
    expect(instituicao).to_be_hidden()
    pg.get_by_role("radio", name=re.compile("^Outra instituição")).check()
    expect(instituicao).to_be_visible()
    # Teclado: setas trocam o meio de transporte (rádios nativos sob os cartões).
    viatura = pg.get_by_role("radio", name=re.compile("^Viatura oficial"))
    viatura.check()
    viatura.focus()
    pg.keyboard.press("ArrowDown")
    expect(pg.get_by_role("radio", name=re.compile("^Outro meio"))).to_be_checked()
    expect(pg.get_by_label("Descrição do transporte")).to_be_visible()
    # Porte de arma é um interruptor.
    expect(pg.get_by_role("switch", name=re.compile("Porte/trânsito de arma"))).to_be_visible()
    # Itinerário: começa e termina na sede; o trecho diz de onde sai.
    paradas = pg.locator("#roteiro .parada")
    expect(paradas.first).to_contain_text("sede · partida")
    expect(paradas.last).to_contain_text("Retorno a")
    expect(pg.locator("#roteiro .parada__trecho").first).to_contain_text("Saída de")
    # Conferência: diz quantas pendências faltam e lista as seções.
    expect(pg.locator("#emissao .conferencia__titulo")).to_contain_text("para emitir")
    expect(pg.locator("#emissao .conferencia__item")).to_have_count(6)


def test_faixa_de_progresso_fica_fixa_e_marca_a_secao_atual(logado, dados_e2e):
    pg = logado
    pg.goto(f"/viagens/oficios/{dados_e2e.ids['oficio_rascunho']}/editar/")
    faixa = pg.locator(".progresso--fixo")
    pg.locator("#roteiro").scroll_into_view_if_needed()
    pg.mouse.wheel(0, 200)
    expect(faixa).to_be_in_viewport()
    expect(faixa).to_have_class(re.compile("progresso--flutuando"))
    expect(faixa.locator("[aria-current='location']")).to_have_count(1)


def test_novo_oficio_abre_a_folha_com_a_placa_a_reservar(logado):
    pg = logado
    pg.goto("/viagens/oficios/novo/")
    expect(pg.locator(".placa--a-reservar")).to_be_visible()
    expect(pg.get_by_role("navigation", name="O que vem depois")).to_contain_text("Conferência")
    expect(pg.get_by_role("button", name="Criar rascunho e continuar")).to_be_visible()
