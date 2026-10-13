"""Roteiro funcional de HOMOLOGAÇÃO no navegador, contra o endereço implantado (HTTPS).

    HOMOLOGACAO_URL=https://homologacao.<domínio> \
    HOMOLOGACAO_USUARIO=demo HOMOLOGACAO_SENHA=… \
    HOMOLOGACAO_CONSULTA_USUARIO=consulta.demo HOMOLOGACAO_CONSULTA_SENHA=… \
    uv run python deploy/homologacao/roteiro_navegador.py

Somente dados sintéticos: o roteiro edita o motivo de um rascunho. Não rode em produção.
Verifica: login com senha → central → painel → lista (paginação, busca, filtro) → resumo e
documentos → download do PDF → edição com autosave → permissões (perfil consulta) → sair;
sem erros de console/HTTP, sem rolagem horizontal e sem requisições a outros hosts
(localhost do computador de desenvolvimento, por exemplo). Larguras 360 e 1440 px.
HOMOLOGACAO_IGNORAR_TLS=1 e HOMOLOGACAO_PROXY_BYPASS=1 só na simulação local (certificado
interno do Caddy; domínio .test fora do proxy de saída).
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ["HOMOLOGACAO_URL"].rstrip("/")
HOST = urlparse(BASE).hostname
# Mosaico do mapa (img-src da CSP) é a única origem externa esperada.
HOSTS_PERMITIDOS = {HOST, "tile.openstreetmap.org"}
LARGURAS = [int(x) for x in os.environ.get("HOMOLOGACAO_LARGURAS", "360,1440").split(",")]
resultado: list[str] = []


def passo(texto: str) -> None:
    resultado.append(texto)
    sys.stdout.write(f"  ok   {texto}\n")


def nova_pagina(navegador, largura: int) -> Page:
    contexto = navegador.new_context(
        viewport={"width": largura, "height": 900}, locale="pt-BR", base_url=BASE,
        timezone_id="America/Sao_Paulo", accept_downloads=True,
        ignore_https_errors=os.environ.get("HOMOLOGACAO_IGNORAR_TLS") == "1")
    pg = contexto.new_page()
    pg.problemas = []  # type: ignore[attr-defined]

    def pedido(r):
        host = urlparse(r.url).hostname
        if r.url.startswith(("http://", "https://")) and host not in HOSTS_PERMITIDOS:
            pg.problemas.append(f"requisição a host externo/indevido: {r.url}")  # type: ignore[attr-defined]

    def resposta(r):
        if r.status >= 400:
            pg.problemas.append(f"HTTP {r.status} {r.url}")  # type: ignore[attr-defined]

    pg.on("request", pedido)
    pg.on("response", resposta)
    pg.on("console", lambda m: m.type == "error" and pg.problemas.append(m.text))  # type: ignore[attr-defined]
    pg.on("pageerror", lambda e: pg.problemas.append(str(e)))  # type: ignore[attr-defined]
    return pg


def sem_rolagem(pg: Page) -> None:
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, pg.url


def entrar(pg: Page, usuario: str, senha: str) -> None:
    pg.goto("/conta/entrar/")
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()
    pg.locator("input[name='username']").fill(usuario)
    pg.locator("input[name='password']").fill(senha)
    pg.get_by_role("button", name="Entrar").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Central de módulos")


def sair(pg: Page) -> None:
    pg.get_by_role("button", name=re.compile("Menu do usuário")).click()
    pg.get_by_role("menuitem", name="Sair").click()
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()


def ir_para(pg: Page, largura: int, item: str) -> None:
    if largura < 768:
        pg.get_by_role("button", name="Abrir menu de navegação").click()
    pg.get_by_role("navigation", name="Navegação principal").get_by_role(
        "link", name=item, exact=True).click()


def total(pg: Page) -> int:
    contagem = pg.locator(".aba[aria-current='page'] .aba__contagem").inner_text()
    return int(re.sub(r"\D", "", contagem))


def roteiro(navegador, largura: int) -> list[str]:
    pg = nova_pagina(navegador, largura)
    sys.stdout.write(f"— {largura}px\n")
    # Sem sessão: protegido.
    pg.goto("/viagens/oficios/")
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()
    expect(pg.get_by_text("Ambiente de demonstração")).to_have_count(0)
    passo("sem sessão → login; sem aviso/entrada DEMO")
    entrar(pg, os.environ["HOMOLOGACAO_USUARIO"], os.environ["HOMOLOGACAO_SENHA"])
    sem_rolagem(pg)
    passo("login com senha → Central de módulos")

    pg.get_by_role("link", name="Entrar no módulo").first.click()
    expect(pg.get_by_role("heading", name="Para concluir")).to_be_visible()
    passo("painel do módulo")

    ir_para(pg, largura, "Ofícios")
    n = total(pg)
    assert n >= 20, n
    pg.get_by_role("link", name="Próxima página").first.click()
    expect(pg.locator(".paginacao")).to_contain_text(f"Mostrando 21–40 de {n}")
    sem_rolagem(pg)
    passo(f"lista com {n} ofícios e paginação")

    busca = pg.get_by_role("searchbox", name="Buscar", exact=True)
    protocolo = pg.locator(".registro__meta-item", has_text="Protocolo").first.inner_text()
    busca.fill(protocolo.replace("Protocolo", "").strip())
    expect(pg.locator("#titulo-resultados")).to_contain_text("Resultados para")
    assert 0 < total(pg) < n
    busca.fill("zzzz-nada-encontrado")
    expect(pg.get_by_text("Nenhum ofício encontrado")).to_be_visible()
    busca.fill("")
    expect(pg.locator("#titulo-resultados")).not_to_contain_text("Resultados para")
    passo("busca ao vivo e estado vazio")

    pg.locator("label[for='documento-emitido']").click()
    expect(pg).to_have_url(re.compile("documento=emitido"))
    passo("filtro por documento emitido")

    pg.locator(".registro__link").first.click()
    janela = pg.get_by_role("dialog", name="Resumo do ofício")
    expect(janela).to_be_visible()
    link_pdf = janela.locator("a[href*='/viagens/documentos/']").first
    expect(link_pdf).to_be_visible()
    href = link_pdf.get_attribute("href")
    resposta = pg.request.get(href + ("&" if "?" in href else "?") + "versao=original")
    assert resposta.status == 200 and resposta.body()[:5] == b"%PDF-", resposta.status
    passo(f"resumo com documentos; PDF baixado ({len(resposta.body())} bytes)")
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()

    pg.goto("/viagens/oficios/?documento=rascunho")
    pg.locator(".registro__link").first.click()
    resumo = pg.get_by_role("dialog", name="Resumo do ofício")
    resumo.get_by_role("link", name="Abrir o ofício").click()
    pg.get_by_label("Motivo da viagem").fill(f"Reunião regional (homologação {largura}px).")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text(
        "Salvo automaticamente às", timeout=15000)
    sem_rolagem(pg)
    passo("edição de rascunho com autosave")
    pg.get_by_role("button", name="Finalizar").click()
    expect(pg.get_by_text(re.compile(r"Ofício \d+/\d{4} salvo\."))).to_be_visible()
    passo("finalizar edição")
    sair(pg)
    pg.goto("/viagens/oficios/")
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()
    passo("sair encerra a sessão")

    if os.environ.get("HOMOLOGACAO_CONSULTA_USUARIO"):
        entrar(pg, os.environ["HOMOLOGACAO_CONSULTA_USUARIO"],
               os.environ["HOMOLOGACAO_CONSULTA_SENHA"])
        r = pg.request.get("/viagens/oficios/novo/", max_redirects=0)
        assert r.status in (302, 403, 404), r.status
        pg.problemas = [p for p in pg.problemas if "/viagens/oficios/novo/" not in p]  # type: ignore[attr-defined]
        passo(f"perfil consulta não cria ofício (HTTP {r.status})")
        sair(pg)

    problemas = list(pg.problemas)  # type: ignore[attr-defined]
    pg.context.close()
    return problemas


def main() -> int:
    falhas: list[str] = []
    with sync_playwright() as p:
        opcoes = {}
        if os.environ.get("HOMOLOGACAO_PROXY_BYPASS") == "1" and os.environ.get("HTTPS_PROXY"):
            opcoes["proxy"] = {"server": os.environ["HTTPS_PROXY"], "bypass": HOST}
        navegador = p.chromium.launch(**opcoes)
        for largura in LARGURAS:
            try:
                falhas += [f"{largura}px: {x}" for x in roteiro(navegador, largura)]
            except Exception as exc:  # relatório do roteiro: segue para a próxima largura
                falhas.append(f"{largura}px: {type(exc).__name__}: {str(exc)[:300]}")
        navegador.close()
    for f in falhas:
        sys.stdout.write(f"  FALHA {f}\n")
    veredito = "tudo ok." if not falhas else f"{len(falhas)} falha(s)."
    sys.stdout.write(f"Roteiro de homologação: {veredito}\n")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
