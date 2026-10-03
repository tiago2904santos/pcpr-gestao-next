"""Evidências visuais ANTES × DEPOIS: captura reprodutível de todas as páginas e estados.

Uso (servidor PREVIEW/DEMO no ar, ex.: scripts/preview.sh local):
  uv run python scripts/evidencias_visuais.py capturar antes  --base http://127.0.0.1:8100
  ...mudanças...
  uv run python scripts/evidencias_visuais.py capturar depois --base http://127.0.0.1:8100
  uv run python scripts/evidencias_visuais.py compor

Saída em artifacts/visual-refinement-v2/{antes,depois}/<cenario>-<largura>.png, um
manifesto JSON por rodada (rota, viewport, estado, dados) e, em `comparacoes/`, as
composições lado a lado + `index.html` (galeria navegável).

A rodada "antes" resolve quais registros DEMO usar (ofício emitido, rascunho, roteiro…) e
grava em dados.json; a rodada "depois" reutiliza exatamente os mesmos.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "artifacts" / "visual-refinement-v2"
LARGURAS = [360, 390, 768, 1024, 1440]
ALTURA = 900

# ---------------------------------------------------------------- estados (interações)


def e_padrao(pg, w):
    pass


def e_login_foco(pg, w):
    pg.keyboard.press("Tab")
    pg.keyboard.press("Tab")


def e_login_erro(pg, w):
    pg.fill("#id_username", "alguem")
    pg.fill("#id_password", "senha-errada")
    pg.get_by_role("button", name="Entrar").click()
    pg.wait_for_load_state("networkidle")


def e_menu_usuario(pg, w):
    pg.locator(".perfil").click()
    pg.wait_for_timeout(350)


def e_paleta(pg, w):
    pg.keyboard.press("Control+k")
    pg.wait_for_timeout(200)
    pg.keyboard.type("of")
    pg.wait_for_timeout(700)


def e_menu_cadastros(pg, w):
    pg.get_by_role("button", name=re.compile("^Cadastros")).click()
    pg.wait_for_timeout(350)


def e_menu_modulo(pg, w):
    pg.locator(".navegacao__seletor").click()
    pg.wait_for_timeout(350)


def e_gaveta(pg, w):
    pg.locator("[data-acao='abrir-gaveta']").click()
    pg.wait_for_timeout(450)


def e_lista_motivo(pg, w):
    """Menu da linha → Cancelar → janela "pedir motivo" (D2/ciclo de vida)."""
    pg.locator(".registro [data-menu-botao]").first.click()
    pg.locator(".menu__painel:not([hidden]) [data-pedir-motivo]").first.click()
    pg.wait_for_timeout(450)


def e_lista_gaveta_filtros(pg, w):
    pg.locator("#filtros-mais summary").click()
    pg.wait_for_timeout(350)


def e_editar_motorista_externo(pg, w):
    """Bloco "Motorista de fora da equipe" aberto em "Pessoa não cadastrada" (sem disparar
    autosave: só a opção marcada muda — o :has() do CSS mostra os campos)."""
    pg.locator(".motorista-externo").scroll_into_view_if_needed()
    pg.evaluate("""() => { const d = document.querySelector('.motorista-externo'); d.open = true;
      document.getElementById('id_motorista_externo').value = 'manual'; }""")
    pg.wait_for_timeout(300)


def e_lista_menu_acoes(pg, w):
    pg.locator(".registro [data-menu-botao]").first.click()
    pg.wait_for_timeout(350)


def e_lista_foco_registro(pg, w):
    pg.locator(".registro__link").first.focus()
    pg.wait_for_timeout(200)


def e_senha_erro(pg, w):
    pg.get_by_role("button", name="Salvar nova senha").click()
    pg.wait_for_load_state("networkidle")


def e_editar_erro(pg, w):
    pg.locator("#id_protocolo").fill("123")
    pg.locator("#id_motivo").fill("")
    pg.get_by_role("button", name=re.compile("^Salvar")).first.click()
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(300)


def e_editar_foco(pg, w):
    pg.locator("#id_motivo").focus()
    pg.wait_for_timeout(250)


def e_editar_calendario(pg, w):
    pg.locator("#roteiro").scroll_into_view_if_needed()
    pg.get_by_role("button", name=re.compile("^Escolher data: Saída")).first.click()
    pg.wait_for_timeout(350)


def e_editar_relogio(pg, w):
    pg.locator("#roteiro").scroll_into_view_if_needed()
    pg.get_by_role("button", name=re.compile("^Escolher hora: Saída")).first.click()
    pg.wait_for_timeout(350)


def e_editar_lista_combustivel(pg, w):
    pg.locator("#id_tipo_transporte-gatilho").click()
    pg.get_by_role("option", name="Outro meio").click()
    pg.locator("#id_transporte_combustivel-gatilho").click()
    pg.wait_for_timeout(350)


def e_editar_menu(pg, w):
    pg.get_by_role("button", name="Mais ações do ofício").click()
    pg.wait_for_timeout(350)


def e_resumo_mais_acoes(pg, w):
    pg.locator("#dialogo-resumo .dialogo__rodape [data-menu-botao]").click()
    pg.wait_for_timeout(350)


def e_itin_calendario(pg, w):
    pg.locator("pc-itinerario").scroll_into_view_if_needed()
    pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="Preencher datas de saída").click()
    pg.wait_for_timeout(350)


def e_itin_arrastando(pg, w):
    pg.locator("pc-itinerario").scroll_into_view_if_needed()
    pg.wait_for_timeout(2500)
    par = pg.locator("[data-parada]:visible")
    if par.count() < 2:
        return
    alca = par.last.locator("[data-alca]")
    alca.scroll_into_view_if_needed()
    a, t = alca.bounding_box(), par.first.bounding_box()
    pg.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(a["x"] + 8, t["y"] + t["height"] * 0.3, steps=10)
    pg.wait_for_timeout(250)


def e_itin_uf(pg, w):
    pg.locator("pc-itinerario").scroll_into_view_if_needed()
    pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="Adicionar destino").click()
    nova = pg.locator("[data-parada]:visible").last
    nova.get_by_role("combobox", name="UF").click()
    pg.get_by_role("option", name="SC", exact=True).click()
    nova.locator("input[name$='-cidade']").fill("Flor")
    pg.wait_for_timeout(700)


def e_mapa(pg, w):
    pg.locator("pc-itinerario").scroll_into_view_if_needed()
    pg.wait_for_timeout(3500)


def e_lab_toast(pg, w):
    pg.get_by_role("button", name="Toast de erro (persistente)").click()
    pg.wait_for_timeout(500)


def e_lab_dialogo(pg, w):
    b = pg.locator("[data-abrir-dialogo]").first
    b.scroll_into_view_if_needed()
    b.click()
    pg.wait_for_timeout(450)


def e_lab_foco_campo(pg, w):
    pg.locator("#campos #id_nome").first.focus()
    pg.wait_for_timeout(250)


ESTADOS = {k[2:]: v for k, v in globals().items() if k.startswith("e_") and callable(v)}

# ---------------------------------------------------------------- cenários
TODAS = LARGURAS
POUCAS = [390, 1440]
DESK = [768, 1440]
MOBILE = [360, 390]


def C(id, titulo, rota, estado="padrao", larguras=TODAS, inteira=True, publico=False,
      recorte=None):
    return {"id": id, "titulo": titulo, "rota": rota, "estado": estado, "larguras": larguras,
            "inteira": inteira, "publico": publico, "recorte": recorte}


CENARIOS = [
    # Públicas
    C("login", "Acesso ao sistema", "/conta/entrar/", publico=True),
    C("login-foco", "Acesso — foco por teclado no campo", "/conta/entrar/", "login_foco", POUCAS, False, True),
    C("login-erro", "Acesso — credenciais inválidas", "/conta/entrar/", "login_erro", POUCAS, True, True),
    C("erro-404", "Página não encontrada", "/nao-existe/", larguras=POUCAS),
    # Shell
    C("central", "Central de módulos", "/"),
    C("central-menu-usuario", "Menu do usuário aberto", "/", "menu_usuario", POUCAS, False),
    C("central-paleta", "Paleta de comandos (Ctrl+K)", "/", "paleta", POUCAS, False),
    C("central-menu-modulo", "Seletor de módulo aberto", "/viagens/", "menu_modulo", DESK, False),
    C("nav-menu-cadastros", "Menu suspenso Cadastros", "/viagens/", "menu_cadastros", DESK, False),
    C("nav-gaveta", "Gaveta de navegação (celular)", "/viagens/", "gaveta", MOBILE, False),
    C("notificacoes", "Notificações (vazio)", "/notificacoes/", larguras=POUCAS),
    C("senha", "Alterar senha", "/conta/senha/", larguras=POUCAS),
    C("senha-erro", "Alterar senha — erros", "/conta/senha/", "senha_erro", POUCAS),
    # Viagens
    C("viagens-painel", "Painel do módulo Viagens", "/viagens/"),
    C("oficios-lista", "Lista de ofícios", "/viagens/oficios/"),
    C("oficios-lista-motivo", "Lista — cancelar pede o motivo", "/viagens/oficios/", "lista_motivo", POUCAS, False),
    C("oficios-lista-filtros", "Lista — Mais filtros (período de saída e data do ofício)", "/viagens/oficios/", "lista_gaveta_filtros", POUCAS, False),
    C("oficios-lista-arquivados", "Lista — aba Arquivados", "/viagens/oficios/?situacao=arquivado", larguras=POUCAS),
    C("oficios-lista-menu", "Lista — menu de ações do registro", "/viagens/oficios/", "lista_menu_acoes", POUCAS, False),
    C("oficios-lista-foco", "Lista — foco por teclado no registro", "/viagens/oficios/", "lista_foco_registro", POUCAS, False),
    C("oficios-lista-rascunhos", "Lista — aba Rascunhos", "/viagens/oficios/?situacao=rascunho", larguras=POUCAS),
    C("oficios-lista-por-saida", "Lista — ordenada por saída", "/viagens/oficios/?ordem=saida&situacao=proximos", larguras=POUCAS),
    C("oficios-lista-vazia", "Lista — busca sem resultado", "/viagens/oficios/?q=nada-encontrado-xyz", larguras=POUCAS),
    # A leitura do ofício é a janela de resumo (ADR 0017): a página de detalhe não existe mais.
    C("oficio-resumo", "Janela de resumo — emitido", "/viagens/oficios/?resumo={oficio_emitido}"),
    C("oficio-resumo-acoes", "Janela de resumo — mais ações", "/viagens/oficios/?resumo={oficio_emitido}", "resumo_mais_acoes", POUCAS, False),
    C("oficio-resumo-cancelado", "Janela de resumo — cancelado (motivo e reativar)", "/viagens/oficios/?situacao=cancelado&resumo={oficio_cancelado}", larguras=POUCAS),
    C("oficio-resumo-rascunho", "Janela de resumo — rascunho com pendências", "/viagens/oficios/?resumo={oficio_rascunho}", larguras=POUCAS),
    C("oficio-editar", "Edição do ofício (rascunho)", "/viagens/oficios/{oficio_rascunho}/editar/", "mapa"),
    C("oficio-editar-erro", "Edição — erros de validação", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_erro", POUCAS),
    C("oficio-editar-foco", "Edição — campo em foco", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_foco", POUCAS, False),
    C("oficio-editar-calendario", "Edição — calendário", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_calendario", POUCAS, False),
    C("oficio-editar-relogio", "Edição — relógio", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_relogio", POUCAS, False),
    C("oficio-editar-lista", "Edição — lista própria (combustível)", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_lista_combustivel", POUCAS, False),
    C("oficio-editar-menu", "Edição — mais ações", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_menu", POUCAS, False),
    C("oficio-editar-pronto", "Edição — ofício pronto para emitir", "/viagens/oficios/{oficio_pronto}/editar/", "mapa", POUCAS),
    C("oficio-revisar", "Revisar e emitir (janela sobre a folha)", "/viagens/oficios/{oficio_pronto}/editar/?revisar=1"),
    C("oficio-motorista-externo", "Edição — motorista de fora da equipe", "/viagens/oficios/{oficio_rascunho}/editar/", "editar_motorista_externo", POUCAS, False),
    C("justificativas", "Justificativas", "/viagens/justificativas/"),
    C("justificativas-pendentes", "Justificativas — pendentes", "/viagens/justificativas/?aba=pendentes", larguras=POUCAS),
    C("numeracao", "Numeração dos ofícios", "/viagens/oficios/numeracao/", larguras=POUCAS),
    # Roteiros
    C("roteiros-lista", "Lista de roteiros", "/viagens/roteiros/"),
    C("roteiros-lista-cancelados", "Roteiros — aba Cancelados", "/viagens/roteiros/?aba=cancelados", larguras=POUCAS),
    C("roteiro-novo", "Novo roteiro", "/viagens/roteiros/novo/"),
    C("roteiro-editar", "Editar roteiro (mapa e trechos)", "/viagens/roteiros/{roteiro}/editar/", "mapa"),
    C("roteiro-calendario", "Roteiro — calendário único das saídas", "/viagens/roteiros/{roteiro}/editar/", "itin_calendario", POUCAS, False),
    C("roteiro-arrastando", "Roteiro — arrastando um destino", "/viagens/roteiros/{roteiro}/editar/", "itin_arrastando", POUCAS, False),
    C("roteiro-uf", "Roteiro — UF filtrando municípios", "/viagens/roteiros/{roteiro}/editar/", "itin_uf", POUCAS, False),
    # Cadastros
    C("cadastros-servidores", "Servidores", "/cadastros/servidores/"),
    C("cadastros-viaturas", "Viaturas", "/cadastros/viaturas/", larguras=POUCAS),
    C("cadastros-diarias", "Tabela de diárias", "/cadastros/diarias/", larguras=POUCAS),
    C("cadastros-textos", "Textos prontos", "/cadastros/textos-prontos/?tipo=motivo", larguras=POUCAS),
    C("cadastros-textos-novo", "Textos prontos — janela de novo texto", "/cadastros/textos-prontos/?tipo=motivo&novo=1", larguras=POUCAS, inteira=False),
    # UI Lab
    C("ui-lab", "UI Lab (catálogo)", "/ui-lab/", larguras=POUCAS),
    C("ui-lab-toast", "UI Lab — toast", "/ui-lab/", "lab_toast", POUCAS, False),
    C("ui-lab-dialogo", "UI Lab — diálogo", "/ui-lab/", "lab_dialogo", POUCAS, False),
    C("ui-lab-foco-campo", "UI Lab — campo em foco", "/ui-lab/", "lab_foco_campo", POUCAS, False),
]

# ---------------------------------------------------------------- infra


def mosaico(route):
    """Mosaicos do mapa passam pelo Python (o Chromium headless não vê o proxy)."""
    url = route.request.url
    if not url.startswith("https://"):  # só mosaicos públicos por HTTPS
        route.abort()
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pcpr-gestao-evidencias/1.0"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            route.fulfill(status=200, body=r.read(), headers={"content-type": "image/png"})
    except Exception:
        route.abort()


def entrar(pg, base):
    pg.goto(f"{base}/conta/entrar/")
    pg.get_by_role("button", name="Entrar").click()
    pg.wait_for_url(lambda u: "/conta/entrar/" not in u)


def resolver_dados(pg, base) -> dict:
    """Escolhe os registros DEMO usados nas capturas (gravados para a rodada "depois")."""
    dados = {}

    def primeiro(url):
        pg.goto(f"{base}{url}", wait_until="networkidle")
        link = pg.locator(".registro a[href]").first
        return link.get_attribute("href") if link.count() else None

    def pk(href):
        m = re.search(r"/(\d+)/", href or "")
        return int(m.group(1)) if m else None

    dados["oficio_emitido"] = pk(primeiro("/viagens/oficios/?situacao=emitido"))
    dados["oficio_cancelado"] = pk(primeiro("/viagens/oficios/?situacao=cancelado"))
    dados["oficio_rascunho"] = pk(primeiro("/viagens/oficios/?situacao=rascunho"))
    # Rascunho pronto para emitir: o primeiro cujo /emitir/ não devolve para a edição.
    pg.goto(f"{base}/viagens/oficios/?situacao=rascunho", wait_until="networkidle")
    hrefs = [a.get_attribute("href") for a in pg.locator(".registro a.registro__link").all()]
    for h in hrefs[:20]:
        pg.goto(f"{base}/viagens/oficios/{pk(h)}/emitir/", wait_until="networkidle")
        if pg.url.rstrip("/").endswith("/emitir"):
            dados["oficio_pronto"] = pk(h)
            break
    dados.setdefault("oficio_pronto", dados["oficio_rascunho"])
    # Roteiro com vários destinos.
    pg.goto(f"{base}/viagens/roteiros/?aba=futuros", wait_until="networkidle")
    escolhido = None
    for i in range(min(pg.locator(".registro").count(), 20)):
        if pg.locator(".registro").nth(i).inner_text().count("→") >= 2:
            escolhido = pg.locator(".registro").nth(i).locator("a.registro__link").get_attribute("href")
            break
    dados["roteiro"] = pk(escolhido or primeiro("/viagens/roteiros/?aba=futuros"))
    dados["roteiro_cancelado"] = pk(primeiro("/viagens/roteiros/?aba=cancelados"))
    return dados


def capturar(rotulo: str, base: str, apenas: list[str] | None, so_erros: bool = False) -> None:
    from playwright.sync_api import sync_playwright

    pasta = SAIDA / rotulo
    pasta.mkdir(parents=True, exist_ok=True)
    arq_dados = SAIDA / "dados.json"
    manifesto: list[dict] = []
    inicio = time.time()
    with sync_playwright() as p:
        nav = p.chromium.launch()

        def contexto(w, logado=True):
            ctx = nav.new_context(viewport={"width": w, "height": ALTURA}, locale="pt-BR",
                                  timezone_id="America/Sao_Paulo", device_scale_factor=1)
            pg = ctx.new_page()
            pg.route("https://tile.openstreetmap.org/**", mosaico)
            pg.erros = []  # type: ignore[attr-defined]
            pg.on("console", lambda m: m.type == "error" and pg.erros.append(m.text))  # type: ignore[attr-defined]
            pg.on("pageerror", lambda e: pg.erros.append(str(e)))  # type: ignore[attr-defined]
            if logado:
                entrar(pg, base)
            return ctx, pg

        if arq_dados.exists():
            dados = json.loads(arq_dados.read_text())
        else:
            ctx, pg = contexto(1440)
            dados = resolver_dados(pg, base)
            ctx.close()
            arq_dados.write_text(json.dumps(dados, indent=2))
        print("dados:", dados)

        pendentes = None
        if so_erros and (pasta / "manifesto.json").exists():  # refaz só os pares (id, largura) com erro
            pendentes = {(c["id"], c["largura"]) for c in json.loads((pasta / "manifesto.json").read_text())["capturas"] if "erro" in c}
        for w in LARGURAS:
            cenarios = [c for c in CENARIOS if w in c["larguras"] and (not apenas or c["id"] in apenas)
                        and (not pendentes or (c["id"], w) in pendentes)]
            if not cenarios:
                continue
            ctx_pub, pg_pub = contexto(w, logado=False)
            ctx, pg = contexto(w)
            for c in cenarios:
                try:
                    url = c["rota"].format(**dados)
                except KeyError as exc:
                    manifesto.append({**c, "largura": w, "url": None, "erro": f"sem dado {exc}"})
                    continue
                if "None" in url:
                    manifesto.append({**c, "largura": w, "url": url, "erro": "registro inexistente na base"})
                    continue
                p_ = pg_pub if c["publico"] else pg
                p_.erros.clear()  # type: ignore[attr-defined]
                arquivo = pasta / f"{c['id']}-{w}.png"
                registro = {"id": c["id"], "titulo": c["titulo"], "url": url, "largura": w,
                            "estado": c["estado"], "arquivo": str(arquivo.relative_to(SAIDA)),
                            "inteira": c["inteira"]}
                try:
                    p_.goto(f"{base}{url}", wait_until="networkidle")
                    p_.wait_for_timeout(250)
                    ESTADOS[c["estado"]](p_, w)
                    p_.mouse.move(w - 1, ALTURA - 1) if c["estado"] == "padrao" else None
                    p_.wait_for_timeout(150)
                    p_.evaluate("document.querySelectorAll('.toast').forEach(t => t.remove())") if c["estado"] == "padrao" else None
                    if c["recorte"]:
                        p_.locator(c["recorte"]).first.screenshot(path=str(arquivo))
                    elif c["inteira"]:
                        # Página inteira sempre a partir do topo: elementos fixos (topo, barra de
                        # ações) ficam onde o leitor espera, não no meio da imagem.
                        p_.evaluate("window.scrollTo(0, 0)")
                        p_.wait_for_timeout(300)
                        p_.screenshot(path=str(arquivo), full_page=True, animations="disabled")
                    else:
                        p_.screenshot(path=str(arquivo), full_page=c["inteira"], animations="disabled")
                    registro["overflow_px"] = p_.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    registro["http"] = p_.url
                except Exception as exc:  # registra e segue: evidência faltante é dado, não falha
                    registro["erro"] = str(exc).splitlines()[0][:200]
                registro["erros_console"] = list(p_.erros)  # type: ignore[attr-defined]
                manifesto.append(registro)
                print(f"{w:>5} {c['id']:<28} {'ERRO ' + registro['erro'] if 'erro' in registro else 'ok'}")
                if c["estado"] != "padrao":
                    # Estados abertos (menus, diálogos) não vazam para o próximo cenário.
                    p_.keyboard.press("Escape")
                    p_.mouse.up()
            ctx.close()
            ctx_pub.close()
        nav.close()
    arq_manifesto = pasta / "manifesto.json"
    if apenas and arq_manifesto.exists():  # rodada parcial: substitui só o que foi refeito
        refeitas = {(m["id"], m["largura"]) for m in manifesto}
        anteriores = json.loads(arq_manifesto.read_text())["capturas"]
        manifesto = [m for m in anteriores if (m["id"], m["largura"]) not in refeitas] + manifesto
    arq_manifesto.write_text(json.dumps({
        "rotulo": rotulo, "base": base, "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duracao_s": round(time.time() - inicio), "dados": dados, "capturas": manifesto,
    }, indent=2, ensure_ascii=False))
    falhas = [m for m in manifesto if "erro" in m]
    print(f"{len(manifesto)} capturas, {len(falhas)} com erro, em {round(time.time() - inicio)}s")


# ---------------------------------------------------------------- composição lado a lado


def _md_para_html(md: str) -> str:
    """Markdown mínimo (títulos, parágrafos, listas, tabelas, código) → HTML da galeria."""
    import html as h

    def inline(s: str) -> str:
        s = h.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    saida, tabela, lista, par = [], [], [], []

    def fecha():
        nonlocal tabela, lista, par
        if tabela:
            cab, *corpo = [r for r in tabela if not re.match(r"^\|?\s*:?-{2,}", r)]
            celulas = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]  # noqa: E731
            saida.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in celulas(cab)) + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in celulas(r)) + "</tr>" for r in corpo) + "</tbody></table>")
            tabela = []
        if lista:
            saida.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in lista) + "</ul>")
            lista = []
        if par:
            saida.append(f"<p>{inline(' '.join(par))}</p>")
            par = []

    for linha in md.splitlines():
        if linha.startswith("|"):
            if par or lista:
                fecha()
            tabela.append(linha)
            continue
        if tabela:
            fecha()
        m = re.match(r"^(#{1,4})\s+(.*)", linha)
        if m:
            fecha()
            n = len(m.group(1)) + 1
            saida.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif re.match(r"^\s*[-*]\s+", linha):
            if par:
                fecha()
            lista.append(re.sub(r"^\s*[-*]\s+", "", linha))
        elif not linha.strip():
            fecha()
        else:
            if lista:
                fecha()
            par.append(linha.strip())
    fecha()
    return "\n".join(saida)


def compor() -> None:
    from PIL import Image, ImageDraw, ImageFont

    antes = json.loads((SAIDA / "antes" / "manifesto.json").read_text())
    depois = json.loads((SAIDA / "depois" / "manifesto.json").read_text())
    por_chave = lambda m: {(c["id"], c["largura"]): c for c in m["capturas"]}  # noqa: E731
    a, d = por_chave(antes), por_chave(depois)
    pasta = SAIDA / "comparacoes"
    pasta.mkdir(exist_ok=True)
    try:
        fonte = ImageFont.truetype(str(RAIZ / "static/fonts/inter-latin-wght-normal.woff2"), 18)
    except Exception:
        fonte = ImageFont.load_default()
    figuras = []
    MAX_ALTURA = 2600
    titulos = {c["id"]: c["titulo"] for c in antes["capturas"]}
    for chave in sorted(a, key=lambda k: (k[0], k[1])):
        ca, cd = a[chave], d.get(chave)
        titulo = f"{ca['titulo']} · {chave[1]}px · estado: {ca['estado']}"
        imagens = []
        for c in (ca, cd):
            if c and "erro" not in c and (SAIDA / c["arquivo"]).exists():
                im = Image.open(SAIDA / c["arquivo"]).convert("RGB")
                if im.height > MAX_ALTURA:
                    im = im.crop((0, 0, im.width, MAX_ALTURA))
                imagens.append(im)
            else:
                imagens.append(None)
        larg = max((im.width for im in imagens if im), default=600)
        alt = max((im.height for im in imagens if im), default=300)
        faixa = 48
        comp = Image.new("RGB", (larg * 2 + 48, alt + faixa + 24), "#f6f5f2")
        dr = ImageDraw.Draw(comp)
        dr.text((16, 12), titulo, fill="#1f1e1b", font=fonte)
        for i, (im, rot) in enumerate(zip(imagens, ("ANTES", "DEPOIS"), strict=True)):
            x = 16 + i * (larg + 16)
            dr.text((x, faixa - 4), rot, fill="#7c6125", font=fonte)
            if im:
                comp.paste(im, (x, faixa + 20))
            else:
                dr.rectangle((x, faixa + 20, x + larg, faixa + 20 + 200), outline="#cbc7be")
                dr.text((x + 12, faixa + 32), "sem captura", fill="#6f6b64", font=fonte)
        nome = f"{chave[0]}-{chave[1]}.jpg"
        comp.save(pasta / nome, quality=82, optimize=True)  # JPEG: a galeria inteira cabe num só envio
        obs = []
        for rot, c in (("antes", ca), ("depois", cd)):
            if c and c.get("erro"):
                obs.append(f"{rot}: {c['erro']}")
            if c and c.get("overflow_px", 0) > 0:
                obs.append(f"{rot}: rolagem horizontal {c['overflow_px']}px")
            if c and [e for e in c.get("erros_console", []) if "404" not in e and "422" not in e]:
                obs.append(f"{rot}: erro de console")
        figuras.append(
            f'<figure id="{chave[0]}-{chave[1]}" data-id="{chave[0]}" data-largura="{chave[1]}">'
            f'<figcaption><strong>{ca["titulo"]}</strong> <code>{ca["url"]}</code> · {chave[1]}px · estado <em>{ca["estado"]}</em>'
            + (f' <span class="obs">{" · ".join(obs)}</span>' if obs else "")
            + f'</figcaption><a href="{nome}"><img loading="lazy" src="{nome}" alt="Antes e depois: {ca["titulo"]} a {chave[1]}px"></a></figure>')
    relatorio = (SAIDA / "relatorio.md").read_text() if (SAIDA / "relatorio.md").exists() else ""
    matriz = (SAIDA / "matriz-cobertura.md").read_text() if (SAIDA / "matriz-cobertura.md").exists() else ""
    ids = sorted({k[0] for k in a})
    html = f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Antes × Depois — refinamento visual V2</title>
<style>
:root{{color-scheme:light}}
body{{font:15px/1.5 Inter,system-ui,sans-serif;margin:0;background:#f6f5f2;color:#1f1e1b}}
header{{position:sticky;top:0;background:#26272b;color:#fff;padding:12px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:2;border-bottom:3px solid #bf9a45}}
header a{{color:#dcc27a}} header select{{font:inherit;padding:6px 10px;border-radius:6px;border:1px solid #57585f}}
main{{padding:16px 24px 48px;max-width:1400px;margin:0 auto}}
section.texto{{background:#fff;border:1px solid #e1ded7;border-radius:12px;padding:8px 24px 16px;margin-bottom:24px}}
section.texto h2{{font-size:22px;margin:16px 0 8px}} section.texto h3{{font-size:17px;margin:16px 0 6px}} section.texto h4{{font-size:15px;margin:12px 0 4px}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}} th,td{{border-bottom:1px solid #e1ded7;padding:6px 8px;text-align:left;vertical-align:top}} th{{background:#fbfaf8;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#5f5b54}}
code{{font-size:12px;background:#f6f5f2;padding:0 4px;border-radius:4px}}
.galeria{{display:grid;gap:28px}}
figure{{margin:0;background:#fff;border:1px solid #e1ded7;border-radius:12px;padding:12px}}
figcaption{{margin-bottom:8px}} .obs{{color:#a3241a;font-size:13px}}
figure img{{width:100%;height:auto;border:1px solid #e1ded7;border-radius:8px;background:#fff}}
.oculto{{display:none}}
</style>
<header><strong>Refinamento visual V2 — Antes × Depois</strong> <span>{len(figuras)} comparações · antes: {antes['gerado_em']} · depois: {depois['gerado_em']}</span>
<label>Página <select id="f-id"><option value="">todas</option>{''.join(f'<option value="{i}">{titulos.get(i, i)}</option>' for i in ids)}</select></label>
<label>Largura <select id="f-w"><option value="">todas</option>{''.join(f'<option>{w}</option>' for w in LARGURAS)}</select></label>
<a href="#galeria">ir para a galeria</a></header>
<main>
<section class="texto" id="relatorio">{_md_para_html(relatorio)}</section>
<section class="texto" id="matriz">{_md_para_html(matriz)}</section>
<div class="galeria" id="galeria">{''.join(figuras)}</div>
</main>
<script>
const fi=document.getElementById('f-id'),fw=document.getElementById('f-w');
function filtrar(){{document.querySelectorAll('figure').forEach(f=>{{f.classList.toggle('oculto',(fi.value&&f.dataset.id!==fi.value)||(fw.value&&f.dataset.largura!==fw.value))}})}}
fi.onchange=fw.onchange=filtrar;
</script></html>"""
    (pasta / "index.html").write_text(html, encoding="utf-8")
    print(f"{len(figuras)} composições em {pasta}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capturar")
    c.add_argument("rotulo", choices=["antes", "depois"])
    c.add_argument("--base", default="http://127.0.0.1:8100")
    c.add_argument("--apenas", default="", help="ids de cenário separados por vírgula")
    sub.add_parser("compor")
    a = p.parse_args()
    if a.cmd == "capturar":
        apenas = [x for x in a.apenas.split(",") if x]
        so_erros = apenas == ["erros"]
        if so_erros:
            m = json.loads((SAIDA / a.rotulo / "manifesto.json").read_text())["capturas"]
            apenas = sorted({c["id"] for c in m if "erro" in c})
        capturar(a.rotulo, a.base, apenas, so_erros)
    else:
        compor()


if __name__ == "__main__":
    sys.exit(main())
