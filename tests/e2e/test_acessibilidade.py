"""WCAG 2.2 AA automático (axe-core) em todas as páginas do piloto."""

from __future__ import annotations

import pytest

from .conftest import entrar, rodar_axe, salvar_relatorio
from .rotas import ROTAS_AUTENTICADAS, ROTAS_PUBLICAS, resolver

pytestmark = pytest.mark.a11y

GRAVES = {"serious", "critical"}


def _avaliar(pg, rota, antes=None):
    pg.goto(rota, wait_until="networkidle")
    if antes is not None:  # ex.: rolar até um componente que carrega ao aparecer
        antes(pg)
    # A barra de ações flutua sobre o fim da tela; o controle que calhar na borda dela sai
    # "pequeno demais" (alvo encoberto), conforme a altura da janela. Mede com a barra em
    # repouso, no lugar dela no fim do formulário (estilo via CSSOM, que a CSP permite) — o
    # campo focado já rola para fora dela (protecao.js); a própria barra continua medida.
    pg.evaluate("document.querySelectorAll('.barra-acoes').forEach(b => b.style.position = 'static')")
    # Janelas que abrem ao carregar entram com animação de escala: medir no meio dela
    # dá alvos menores do que são. Espera as animações finitas acabarem (as infinitas, como
    # o pulso de "processando", ficam de fora).
    pg.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running'"
                         " || a.effect.getTiming().iterations === Infinity)")
    violacoes = rodar_axe(pg)
    graves = [v for v in violacoes if v["impact"] in GRAVES]
    salvar_relatorio(f"axe-{rota.strip('/').replace('/', '_') or 'raiz'}.json", violacoes)
    detalhes = [(v["id"], v["help"], [n["target"] for n in v["nodes"]][:3]) for v in graves]
    assert not graves, f"{rota}: {detalhes}"


@pytest.mark.parametrize("rota", ROTAS_PUBLICAS)
def test_paginas_publicas_sem_violacoes_graves(pagina, rota):
    _avaliar(pagina, rota)


@pytest.mark.parametrize("rota", ROTAS_AUTENTICADAS)
def test_paginas_autenticadas_sem_violacoes_graves(logado, dados_e2e, rota):
    _avaliar(logado, resolver(rota, dados_e2e.ids))


@pytest.mark.parametrize("rota", ["/viagens/oficios/numeracao/",
                                  "/cadastros/textos-prontos/?tipo=motivo",
                                  "/cadastros/diarias/?novo=1",
                                  "/cadastros/configuracao/"])
def test_telas_do_gestor_sem_violacoes_graves(pagina, dados_e2e, rota):
    """Telas que só o gestor abre (numeração; padrão dos textos prontos; nova vigência de
    diária; configuração da unidade editável)."""
    entrar(pagina, "gestor")
    _avaliar(pagina, rota)


def _carregar_previa(pg):
    pg.locator("#previa").scroll_into_view_if_needed()
    # Espera o conteúdo da folha (não a rede ociosa): com a suíte inteira em paralelo a
    # máquina fica carregada e o visualizador demora a carregar.
    pg.locator("iframe[data-quadro='texto']:not([hidden])").wait_for()
    pg.frame_locator("iframe[data-quadro='texto']").locator("body main").wait_for()


@pytest.mark.parametrize("largura", [360, 1440])
def test_folhas_de_termo_os_e_plano_sem_violacoes(logado, dados_e2e, largura):
    """Folhas salvas de termo, OS e plano (cartões, conferência, visualizador e histórico), com o
    visualizador já carregado (ele só carrega ao chegar à tela)."""
    from gestao.identidade.models import Usuario
    from gestao.viagens import ordens, planos, termos
    from gestao.viagens.models import Oficio

    operador = Usuario.objects.get(login="operador")
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    termo = termos.salvar(operador, oficio=oficio)
    ordem, _ = ordens.salvar(operador, oficios=[oficio])
    plano, _ = planos.salvar(operador, oficios=[oficio])
    logado.set_viewport_size({"width": largura, "height": 900})
    logado.set_default_timeout(60_000)  # duas folhas com visualizador; suíte paralela pesa
    logado.set_default_navigation_timeout(60_000)
    for rota in (f"/viagens/termos/{termo.pk}/", f"/viagens/ordens/{ordem.pk}/",
                 f"/viagens/planos/{plano.pk}/"):
        _avaliar(logado, rota, antes=_carregar_previa)
    _avaliar(logado, f"/viagens/planos/{plano.pk}/?evento=novo")  # janela do evento aberta


@pytest.mark.parametrize("largura", [360, 1440])
def test_ui_lab_sem_violacoes_em_todas_as_larguras(logado, largura):
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/ui-lab/")


def _rgb(token: str) -> str:
    from scripts import contraste

    hexa = contraste.valores()[token]
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def _foco(pg, seletor: str) -> dict:
    alvo = pg.locator(seletor).first
    alvo.focus()
    pg.keyboard.press("Shift+Tab")
    pg.keyboard.press("Tab")
    pg.wait_for_timeout(400)  # transições de borda/halo (--duracao-rapida) terminam
    return alvo.evaluate("""e => { const s = getComputedStyle(e);
        return {outline: s.outlineStyle, cor: s.outlineColor, largura: s.outlineWidth,
                offset: s.outlineOffset, borda: s.borderColor, sombra: s.boxShadow}; }""")


def test_foco_por_teclado_e_a_assinatura_do_sistema_nao_o_anel_do_navegador(logado, dados_e2e):
    """Overdrive 2: anel grafite com halo claro no conteúdo; dourado sobre o cabeçalho;
    campos acendem (borda grafite + halo) em vez de anel externo. Nunca azul."""
    pg = logado
    pg.goto("/viagens/oficios/")
    botao = _foco(pg, ".barra-acoes .botao--primario")  # "Novo ofício" acompanha a rolagem
    assert botao["outline"] == "solid" and botao["cor"] == _rgb("--grafite-900"), botao
    assert botao["largura"] == "2px" and botao["offset"] == "2px", botao
    assert _rgb("--neutro-0") in botao["sombra"], botao  # halo claro no vão

    cabecalho = _foco(pg, ".cabecalho__botao")
    assert cabecalho["cor"] == _rgb("--dourado-300"), cabecalho
    assert _rgb("--grafite-950") in cabecalho["sombra"], cabecalho

    campo = _foco(pg, "#busca-oficios")
    assert campo["outline"] == "none" and campo["borda"] == _rgb("--grafite-800"), campo
    assert campo["sombra"] != "none", campo  # halo dourado

    registro = _foco(pg, ".registro__link")
    linha = pg.locator(".registro").first.evaluate("e => getComputedStyle(e).boxShadow")
    assert registro["outline"] == "none" and _rgb("--grafite-900") in linha, (registro, linha)

    # Nenhum estilo de foco computado usa o azul do navegador/DS antigo.
    azul = _rgb("--azul-600")
    for estilo in (botao, cabecalho, campo, registro):
        assert azul not in estilo["cor"] and azul not in estilo["sombra"] and azul not in estilo["borda"]


@pytest.mark.parametrize("largura", [360, 1440])
def test_termo_salvo_com_documentos_sem_violacoes(logado, dados_e2e, largura):
    """A tela de um termo já salvo (herança do ofício à vista e a lista de documentos)."""
    from gestao.identidade.models import Usuario
    from gestao.viagens import termos
    from gestao.viagens.models import Oficio

    termo = termos.salvar(Usuario.objects.get(login="operador"),
                          oficio=Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]))
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/termos/{termo.pk}/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_ordem_com_funcoes_sem_violacoes(logado, dados_e2e, largura):
    """A tela de uma OS salva de tipo com funções (campos de função da equipe à vista)."""
    from gestao.identidade.models import Usuario
    from gestao.viagens import ordens
    from gestao.viagens.models import Oficio

    ordem, _ = ordens.salvar(Usuario.objects.get(login="operador"), tipo="caminhao",
                             oficios=[Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])])
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/ordens/{ordem.pk}/")
