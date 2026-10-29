"""E2E do link de km (fluxo 10-4) no navegador: um trecho salvo com rede vai direto para o
sistema; outro salvo sem rede fica "salvo neste aparelho" e sobe sozinho quando a conexão
volta (conferido no banco) — mais axe sem violações graves e sem rolagem horizontal em 360 e
1440 px. O link é criado direto (`links.criar`, escopo km), como o envio faria."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

from .conftest import rodar_axe

pytestmark = pytest.mark.e2e
SALVO_NO_SISTEMA = re.compile("salvo no sistema", re.IGNORECASE)
SALVO_AQUI = re.compile("salvo neste aparelho", re.IGNORECASE)


def _link(dados) -> tuple[str, list]:
    from gestao.automacao import links
    from gestao.identidade.models import Usuario
    from gestao.viagens import diario, km_link
    from gestao.viagens.models import Oficio

    oficio = Oficio.objects.get(pk=dados.ids["oficio_emitido"])
    d = diario.obter(oficio.prestacao)
    motorista = km_link.responsavel(d)
    _, token = links.criar(escopo="km", recurso=km_link.recurso(d.pk),
                           servidor_id=motorista.pk,
                           criado_por=Usuario.objects.get(login="operador"))
    return f"/p/{token}/", diario.linhas(d)


def _trecho(pg, linha):
    return pg.locator(f"form[data-km-form][data-linha='{linha.pk}']")


def test_km_offline_sincroniza_quando_a_rede_volta(pagina, dados_e2e):
    from gestao.viagens.models import DiarioBordoTrecho

    caminho, linhas = _link(dados_e2e)
    ida, volta = linhas[0], linhas[1]
    pg = pagina
    pg.goto(caminho)
    expect(pg.get_by_role("heading", name="Quilometragem da viagem")).to_be_visible()

    # Com rede: vai direto para o sistema.
    form = _trecho(pg, ida)
    form.get_by_label("Km na saída").fill("45210")
    form.get_by_label("Km na chegada").fill("45590")
    form.get_by_role("button", name="Salvar este trecho").click()
    expect(form.locator("[data-km-estado]")).to_have_text(SALVO_NO_SISTEMA)
    ida.refresh_from_db()
    assert (ida.km_inicial, ida.km_final) == (45210, 45590)

    # Sem rede: fica guardado no aparelho e a página diz isso.
    pg.context.set_offline(True)
    form = _trecho(pg, volta)
    form.get_by_label("Km na saída").fill("45600")
    form.get_by_label("Km na chegada").fill("45980")
    form.get_by_role("button", name="Salvar este trecho").click()
    expect(form.locator("[data-km-estado]")).to_have_text(SALVO_AQUI)
    expect(pg.locator("[data-km-rede]")).to_be_visible()
    volta.refresh_from_db()
    assert volta.km_inicial is None and volta.km_final is None
    pendente = pg.evaluate("""() => Object.keys(localStorage)
        .filter(k => k.startsWith('pcpr-km:v1:')).length""")
    assert pendente == 1

    # A rede volta: sobe sozinho, uma vez.
    pg.context.set_offline(False)
    expect(form.locator("[data-km-estado]")).to_have_text(SALVO_NO_SISTEMA, timeout=15_000)
    volta = DiarioBordoTrecho.objects.get(pk=volta.pk)
    assert (volta.km_inicial, volta.km_final) == (45600, 45980)
    assert pg.evaluate("""() => Object.keys(localStorage)
        .filter(k => k.startsWith('pcpr-km:v1:')).length""") == 0
    graves = [e for e in pg.erros_console  # type: ignore[attr-defined]
              if "net::" not in e and "Failed to load" not in e]
    assert not graves, graves


def test_km_axe_e_sem_rolagem_horizontal(pagina, dados_e2e):
    caminho, _ = _link(dados_e2e)
    pg = pagina
    pg.goto(caminho)
    graves = [v for v in rodar_axe(pg) if v["impact"] in ("serious", "critical")]
    assert not graves, [(v["id"], v["nodes"][0]["target"]) for v in graves]
    for largura in (360, 1440):
        pg.set_viewport_size({"width": largura, "height": 900})
        pg.goto(caminho)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{largura}px: rolagem horizontal de {excesso}px"


def test_km_enter_salva_e_erro_longo_nao_vaza_a_360(pagina, dados_e2e):
    """Revisão de acessibilidade: Enter no campo salva o trecho (o botão de conflito, escondido,
    vinha antes do Salvar no formulário); a frase de erro quebra linha em 360 px; só o trecho
    salvo é anunciado na região viva da página."""
    from gestao.viagens.models import DiarioBordoTrecho

    caminho, linhas = _link(dados_e2e)
    pg = pagina
    pg.set_viewport_size({"width": 360, "height": 800})
    pg.goto(caminho)
    form = _trecho(pg, linhas[0])
    form.get_by_label("Km na saída").fill("12abc")
    form.get_by_label("Km na saída").press("Enter")
    expect(form.locator("[data-km-estado]")).to_contain_text("Use só números")
    largura = pg.evaluate("() => document.documentElement.scrollWidth")
    assert largura <= 360, largura
    form.get_by_label("Km na saída").fill("1000")
    form.get_by_label("Km na chegada").fill("1200")
    form.get_by_label("Km na chegada").press("Enter")
    expect(form.locator("[data-km-estado]")).to_have_text(SALVO_NO_SISTEMA)
    linha = DiarioBordoTrecho.objects.get(pk=linhas[0].pk)
    assert (linha.km_inicial, linha.km_final) == (1000, 1200)
    expect(pg.locator("[data-km-anuncio]")).to_contain_text("Salvo no sistema")
    assert pg.locator("[data-km-estado][role=status], p[role=status] [data-km-estado]").count() == 0


def _sem_service_worker(navegador, live_server):
    """Contexto próprio, sem service worker: o que se testa é o km-offline.js e o servidor."""
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, locale="pt-BR",
                                     timezone_id="America/Sao_Paulo", base_url=live_server.url,
                                     service_workers="block")
    return contexto, contexto.new_page()


def _guardar_sem_rede(pg, linha) -> None:
    pg.context.set_offline(True)
    form = _trecho(pg, linha)
    form.get_by_label("Km na saída").fill("45600")
    form.get_by_label("Km na chegada").fill("45980")
    form.get_by_role("button", name="Salvar este trecho").click()
    expect(form.locator("[data-km-estado]")).to_have_text(SALVO_AQUI)


def _cookie_trocado(pg, live_server) -> None:
    """Outro login na mesma origem trocou o cookie CSRF: o token da página não vale mais."""
    pg.context.add_cookies([{"name": "pcpr_csrf", "value": "x" * 32, "url": live_server.url}])


def test_km_403_de_csrf_renova_o_token_e_envia(navegador, live_server, dados_e2e):
    from gestao.viagens.models import DiarioBordoTrecho

    caminho, linhas = _link(dados_e2e)
    contexto, pg = _sem_service_worker(navegador, live_server)
    try:
        pg.goto(caminho)
        _guardar_sem_rede(pg, linhas[1])
        _cookie_trocado(pg, live_server)
        respostas: list[int] = []
        pg.on("response", lambda r: r.url.endswith("/salvar/") and respostas.append(r.status))
        pg.context.set_offline(False)
        form = _trecho(pg, linhas[1])
        expect(form.locator("[data-km-estado]")).to_have_text(SALVO_NO_SISTEMA, timeout=15_000)
        assert respostas[:2] == [403, 200], respostas  # recusou, renovou o token, enviou
        linha = DiarioBordoTrecho.objects.get(pk=linhas[1].pk)
        assert (linha.km_inicial, linha.km_final) == (45600, 45980)
    finally:
        contexto.close()


def test_km_403_que_persiste_avisa_e_guarda_o_que_foi_salvo(navegador, live_server, dados_e2e):
    from gestao.viagens.models import DiarioBordoTrecho

    caminho, linhas = _link(dados_e2e)
    contexto, pg = _sem_service_worker(navegador, live_server)
    try:
        pg.goto(caminho)
        _guardar_sem_rede(pg, linhas[1])
        pg.route("**/salvar/", lambda rota: rota.fulfill(
            status=403, content_type="text/html", body="<h1>Forbidden (CSRF)</h1>"))
        pg.context.set_offline(False)
        expect(pg.locator("[data-km-rede-texto]")).to_contain_text(
            "Abra este link de novo com internet", timeout=15_000)
        expect(pg.locator("[data-km-rede]")).to_be_visible()
        assert pg.evaluate("""() => Object.keys(localStorage)
            .filter(k => k.startsWith('pcpr-km:v1:')).length""") == 1
        linha = DiarioBordoTrecho.objects.get(pk=linhas[1].pk)
        assert linha.km_inicial is None and linha.km_final is None
    finally:
        contexto.close()


def test_km_digitado_durante_o_envio_nao_e_apagado(navegador, live_server, dados_e2e):
    """A pessoa salva a saída e, enquanto o envio está em voo, digita a chegada: a resposta
    do sistema atualiza só o campo enviado — a chegada digitada continua no campo."""
    from gestao.viagens.models import DiarioBordoTrecho

    caminho, linhas = _link(dados_e2e)
    contexto, pg = _sem_service_worker(navegador, live_server)
    try:
        pg.goto(caminho)
        presas: list = []
        pg.route("**/salvar/", lambda rota: presas.append(rota))  # segura o envio
        form = _trecho(pg, linhas[0])
        form.get_by_label("Km na saída").fill("45210")
        form.get_by_role("button", name="Salvar este trecho").click()
        expect(form.locator("[data-km-estado]")).to_have_text("Enviando…")
        form.get_by_label("Km na chegada").fill("45590")
        while not presas:
            pg.wait_for_timeout(50)
        presas[0].continue_()
        expect(form.locator("[data-km-estado]")).to_have_text(SALVO_NO_SISTEMA)
        expect(form.get_by_label("Km na saída")).to_have_value("45210")
        expect(form.get_by_label("Km na chegada")).to_have_value("45590")
        linha = DiarioBordoTrecho.objects.get(pk=linhas[0].pk)
        assert (linha.km_inicial, linha.km_final) == (45210, None)
    finally:
        contexto.close()
