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
    _avaliar(logado, f"/viagens/planos/{plano.pk}/resultados/")


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


@pytest.mark.parametrize("largura", [360, 1440])
def test_via_assinada_sem_violacoes(logado, dados_e2e, largura):
    """A via assinada nas três telas que a recebem (resumo do ofício, termo e OS), a janela
    de anexar aberta e a página de anexar sem a janela."""
    from gestao.identidade.models import Usuario
    from gestao.plataforma import outbox
    from gestao.viagens import assinados, ordens, termos
    from gestao.viagens.models import Oficio

    while outbox.processar_lote():
        pass
    operador = Usuario.objects.get(login="operador")
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    pdf = b"%PDF-1.7\n%%EOF\n"
    assinados.anexar(operador, assinados.Alvo("oficio", oficio), nome="oficio.pdf", conteudo=pdf)
    termo = termos.salvar(operador, oficio=oficio)
    assinados.anexar(operador, assinados.Alvo("termo", termo, termos.GENERICO), nome="t.pdf",
                     conteudo=pdf)
    ordem, _ = ordens.salvar(operador, oficios=[oficio])
    ordens.dados_do_documento(ordem, fixar=True)
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/oficios/?resumo={oficio.pk}")
    _avaliar(logado, f"/viagens/termos/{termo.pk}/")

    def abrir_janela(pg):
        pg.locator("#via-assinada").get_by_role("link", name="Anexar via assinada").click()
        pg.get_by_role("dialog", name="Anexar via assinada").wait_for()
    _avaliar(logado, f"/viagens/ordens/{ordem.pk}/", antes=abrir_janela)
    _avaliar(logado, f"/viagens/assinados/ordem/{ordem.pk}/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_janela_baixar_documentos_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.viagens import termos
    from gestao.viagens.models import Oficio

    termo = termos.salvar(Usuario.objects.get(login="operador"),
                          oficio=Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"]))
    logado.set_viewport_size({"width": largura, "height": 900})

    def abrir(pg):
        pg.get_by_role("button", name=f"Ações do {termo}").click()
        pg.get_by_role("menuitem", name="Baixar documentos").press("Enter")
        pg.locator("#dialogo-baixar input[name=itens]").first.wait_for()
    _avaliar(logado, "/viagens/termos/", antes=abrir)


@pytest.mark.parametrize("largura", [360, 1440])
def test_central_de_notificacoes_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.plataforma.models import Notificacao
    from gestao.plataforma.notificacoes import notificar

    operador = Usuario.objects.get(login="operador")
    notificar([operador], "Aviso novo de teste", "Mensagem do aviso.", "/viagens/")
    [lido] = notificar([operador], "Aviso lido de teste")
    Notificacao.objects.filter(pk=lido.pk).update(lida=True)
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/notificacoes/")
    _avaliar(logado, "/notificacoes/?filtro=lidas")


@pytest.mark.parametrize("largura", [360, 1440])
def test_usuarios_e_perfis_sem_violacoes(pagina, dados_e2e, largura):
    """Gestão de usuários (só o administrador): lista e a janela de novo usuário aberta."""
    from django.contrib.auth.models import Group

    from gestao.identidade.models import Usuario

    from .conftest import SENHA
    admin = Usuario.objects.create_user("admin", "admin@pc.pr.gov.br", SENHA, nome="Admin E2E")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    entrar(pagina, "admin")
    pagina.set_viewport_size({"width": largura, "height": 900})
    _avaliar(pagina, "/cadastros/usuarios/")
    _avaliar(pagina, "/cadastros/usuarios/?novo=1")


@pytest.mark.parametrize("largura", [360, 1440])
def test_viagem_lista_e_folha_sem_violacoes(logado, dados_e2e, largura):
    from gestao.cadastros.models import TipoViagem
    from gestao.identidade.models import Usuario
    from gestao.viagens import viagem
    from gestao.viagens.models import Oficio

    operador = Usuario.objects.get(login="operador")
    TipoViagem.objects.create(nome="PCPR na Comunidade")
    v = viagem.criar(operador)
    oficio = Oficio.objects.get(pk=dados_e2e.ids["oficio_emitido"])
    viagem.salvar_dados(operador, v.pk, tipos=list(TipoViagem.objects.all()),
                        vinculos={"oficios": [oficio]})
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/viagens/viagens/")
    _avaliar(logado, f"/viagens/viagens/{v.pk}/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_gerar_documentos_da_viagem_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.viagens import viagem

    v = viagem.criar(Usuario.objects.get(login="operador"))
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/viagens/{v.pk}/gerar-documentos/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_prestacao_de_contas_sem_violacoes(logado, dados_e2e, largura):
    """Lista da prestação com um servidor em aberto (campos do lote) e um finalizado."""
    from gestao.identidade.models import Usuario
    from gestao.viagens import prestacao
    from gestao.viagens.models import PrestacaoServidor

    operador = Usuario.objects.get(login="operador")
    a = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=dados_e2e.ids["oficio_emitido"]).order_by("servidor__nome").first()
    prestacao.finalizar(operador, a.pk, "Exemplo de justificativa (teste).")
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/viagens/prestacoes/")
    _avaliar(logado, "/viagens/prestacoes/?aba=finalizados")


@pytest.mark.parametrize("largura", [360, 1440])
def test_diario_de_bordo_sem_violacoes(logado, dados_e2e, largura):
    from gestao.viagens.models import PrestacaoContas

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/prestacoes/equipe/{p.pk}/diario/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_relatorio_tecnico_sem_violacoes(logado, dados_e2e, largura):
    from gestao.viagens.models import PrestacaoContas

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/prestacoes/equipe/{p.pk}/relatorio/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_documentos_da_prestacao_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.viagens import anexos
    from gestao.viagens.models import PrestacaoContas, PrestacaoServidor

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    anexos.anexar(Usuario.objects.get(login="operador"), p.pk, "comprovante", servidor_pk=a.pk,
                  nome="comprovante.pdf", conteudo=b"%PDF-1.4 t")
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/prestacoes/equipe/{p.pk}/documentos/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_diario_com_viagem_realizada_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.viagens import realizado
    from gestao.viagens.models import PrestacaoContas

    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    realizado.ajustar(Usuario.objects.get(login="operador"), p.pk)
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/prestacoes/equipe/{p.pk}/diario/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_documentos_com_carimbo_sem_violacoes(logado, dados_e2e, largura):
    from gestao.identidade.models import Usuario
    from gestao.plataforma import outbox
    from gestao.viagens import assinados, prestacao
    from gestao.viagens.models import Oficio, PrestacaoContas, ViaAssinada

    while outbox.processar_lote():
        pass
    operador = Usuario.objects.get(login="operador")
    p = PrestacaoContas.objects.get(oficio_id=dados_e2e.ids["oficio_emitido"])
    oficio = Oficio.objects.get(pk=p.oficio_id)
    with assinados.documento_emitido(oficio, "oficio").arquivo.open("rb") as f:
        assinados.anexar(operador, assinados.Alvo(ViaAssinada.Tipo.OFICIO, oficio),
                         nome="oficio-assinado.pdf", conteudo=f.read())
    a = prestacao.ativos().filter(prestacao=p).order_by("servidor__nome").first()
    prestacao.salvar_solicitacao(operador, a.pk, numero="2030/1", liberacao=None, prazo=None)
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, f"/viagens/prestacoes/equipe/{p.pk}/documentos/")


@pytest.mark.parametrize("largura", [360, 1440])
def test_agenda_sem_violacoes(logado, dados_e2e, largura):
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.viagens import viagem
    from gestao.viagens.models import Viagem

    v = viagem.criar(Usuario.objects.get(login="operador"))
    Viagem.objects.filter(pk=v.pk).update(data_inicio=timezone.localdate(), titulo="Feira",
                                          motivo="Apoio (axe)")
    logado.set_viewport_size({"width": largura, "height": 900})
    _avaliar(logado, "/agenda/")
    _avaliar(logado, "/agenda/?vista=lista")


@pytest.mark.parametrize("largura", [360, 1440])
def test_imprensa_sem_violacoes(logado, dados_e2e, largura):
    from datetime import timedelta

    from django.contrib.auth.models import Group
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.imprensa import services
    from gestao.imprensa.models import Integrante, Veiculo

    u = Usuario.objects.get(login="operador")
    for papel in ("ASCOM_IMPRENSA", "ADMINISTRADOR"):
        u.groups.add(Group.objects.get(name=papel))
    hoje = timezone.localdate()
    rpc = Veiculo.objects.create(nome="RPC")
    mariana = Integrante.objects.create(nome="Mariana")
    a = services.criar(u, {"data": hoje, "jornalista": "Ana (axe)", "pedido": "Dados (axe)",
                           "veiculo": rpc, "responsavel": mariana,
                           "deadline": hoje + timedelta(days=1), "fonte": "Del. A\n\nIML",
                           "inicio_pedido": "09h\n\n10h", "resposta": "Nota"})
    services.registrar_andamento(u, a.pk, "aguardando_fonte", "Fonte acionada")
    logado.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/imprensa/", "/imprensa/atendimentos/", f"/imprensa/atendimentos/{a.pk}/",
                 "/imprensa/atendimentos/novo/", "/imprensa/cadastros/equipe/"):
        _avaliar(logado, rota)
