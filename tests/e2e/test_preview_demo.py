"""E2E do ambiente PREVIEW com a base DEMO populosa (ADR 0011).

LOGIN (campos vazios) → PAINEL → LISTA POPULOSA → PAGINAÇÃO → BUSCA → FILTRO → ORDENAR →
ABRIR OFÍCIO → HISTÓRICO → DOCUMENTOS → VOLTAR → NOVA BUSCA → EDITAR E SALVAR → SAIR → LOGIN,
em 360/390/768/1024/1280/1440 px, sem erros de console/HTTP, sem rolagem horizontal e com
o orçamento de consultas SQL (Server-Timing).

- Local (padrão): sobe o servidor de teste com DEMO ativo e semeia a base DEMO.
- Contra um preview publicado: `PREVIEW_URL=https://… uv run pytest tests/e2e/test_preview_demo.py`
  (ou `scripts/preview.sh verificar`). A edição salva altera o motivo de um rascunho DEMO.
"""

from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Browser, Page, expect

from .conftest import LARGURAS

PREVIEW_URL = os.environ.get("PREVIEW_URL", "").rstrip("/")
# Local: banco de teste transacional (o servidor de teste roda em outra conexão).
pytestmark = [pytest.mark.e2e] + ([] if PREVIEW_URL else [pytest.mark.django_db(transaction=True)])
ORCAMENTO_SQL = 25


@pytest.fixture
def base(request, settings) -> str:
    if PREVIEW_URL:
        return PREVIEW_URL
    from django.db import transaction

    from gestao.viagens import demonstracao
    from gestao.viagens.assinantes import gerar_documento
    from gestao.viagens.models import Documento

    demonstracao.semear(escala=0.3)  # ~78 ofícios: 4 páginas
    for doc in Documento.objects.order_by("-oficio__ano", "-oficio__numero")[:6]:
        with transaction.atomic():  # como no worker da outbox
            gerar_documento({"documento_id": doc.pk})
    settings.APP_ENV = "preview"
    settings.DEMO_MODE = True
    settings.AUTHENTICATION_BACKENDS = [*settings.AUTHENTICATION_BACKENDS,
                                        "gestao.identidade.backends.DemoBackend"]
    return request.getfixturevalue("live_server").url


def _pagina(navegador: Browser, base: str, largura: int) -> Page:
    contexto = navegador.new_context(viewport={"width": largura, "height": 900}, locale="pt-BR",
                                     timezone_id="America/Sao_Paulo", base_url=base)
    pg = contexto.new_page()
    pg.problemas = []  # type: ignore[attr-defined]

    def resposta(r):
        if r.status >= 400:
            pg.problemas.append(f"HTTP {r.status} {r.url}")  # type: ignore[attr-defined]
        timing = r.headers.get("server-timing", "")
        consultas = re.search(r'"(\d+) consultas"', timing)
        if consultas and int(consultas.group(1)) > ORCAMENTO_SQL:
            pg.problemas.append(f"{consultas.group(1)} consultas em {r.url}")  # type: ignore[attr-defined]

    pg.on("response", resposta)
    pg.on("console", lambda m: m.type == "error" and pg.problemas.append(m.text))  # type: ignore[attr-defined]
    pg.on("pageerror", lambda e: pg.problemas.append(str(e)))  # type: ignore[attr-defined]
    return pg


def _sem_rolagem_lateral(pg: Page) -> None:
    assert pg.evaluate("document.documentElement.scrollWidth - innerWidth") <= 0, pg.url


def _ir_para(pg: Page, largura: int, item: str) -> None:
    """Menu superior (≥768) ou gaveta do celular (<768)."""
    if largura < 768:
        pg.get_by_role("button", name="Abrir menu de navegação").click()
    pg.get_by_role("navigation", name="Navegação principal").get_by_role(
        "link", name=item, exact=True).click()


ABA_ATUAL = ".aba[aria-current='page'] .aba__contagem"


def _total(pg: Page) -> int:
    """Quantos ofícios a lista mostra: a contagem da aba atual acompanha busca e filtros."""
    return int(re.sub(r"\D", "", pg.locator(ABA_ATUAL).inner_text()))


@pytest.mark.parametrize("largura", LARGURAS)
def test_fluxo_demo_com_base_populosa(navegador, base, largura):
    pg = _pagina(navegador, base, largura)
    busca = pg.get_by_role("searchbox", name="Buscar", exact=True)

    # Login real do produto, campos vazios.
    pg.goto("/conta/entrar/")
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()
    expect(pg.get_by_text("Ambiente de demonstração")).to_be_visible()
    pg.get_by_role("button", name="Entrar").click()
    expect(pg.get_by_role("heading", level=1)).to_have_text("Central de módulos")
    _sem_rolagem_lateral(pg)

    # Painel do módulo com indicadores e listas preenchidas.
    pg.get_by_role("link", name="Entrar no módulo").first.click()
    expect(pg.get_by_role("heading", name="Para concluir")).to_be_visible()
    expect(pg.locator(".registro").first).to_be_visible()
    _sem_rolagem_lateral(pg)

    # Lista populosa, paginação.
    _ir_para(pg, largura, "Ofícios")
    total = _total(pg)
    assert total >= 60
    expect(pg.locator(".registro")).to_have_count(20)
    pg.get_by_role("link", name="Próxima página").first.click()
    expect(pg.locator(".paginacao")).to_contain_text(f"Mostrando 21–40 de {total}")
    _sem_rolagem_lateral(pg)

    # Busca, filtro e ordenação.
    protocolo = pg.locator(".registro__meta-item", has_text="Protocolo").first.inner_text()
    busca.fill(protocolo.replace("Protocolo", "").strip())
    expect(pg.locator("#titulo-resultados")).to_contain_text("Resultados para")
    assert 0 < _total(pg) < total
    busca.fill("")
    # A busca é ao vivo: espera a lista voltar ao todo antes de filtrar.
    expect(pg.locator("#titulo-resultados")).not_to_contain_text("Resultados para")
    expect(pg.locator(ABA_ATUAL)).to_have_text(str(total))
    pg.locator("label[for='documento-emitido']").click()  # Documento: um clique
    expect(pg).to_have_url(re.compile("documento=emitido"))
    expect(pg.locator(ABA_ATUAL)).not_to_have_text(str(total))
    emitidos = _total(pg)
    assert 0 < emitidos < total
    pg.locator("#filtros-mais > summary").click()  # a ordem mora na gaveta
    pg.get_by_role("combobox", name="Ordenar por").click()
    pg.get_by_role("option", name="Saída, mais antiga primeiro").click()
    expect(pg).to_have_url(re.compile("ordem=saida"))
    pg.locator("[data-fechar-filtros]").click()
    expect(pg.locator(".filtros-ativos")).to_contain_text("Ordem: Saída")
    _sem_rolagem_lateral(pg)

    # Ofício emitido: a leitura é a janela de resumo, com documentos, sem sair da lista.
    pg.locator(".registro__link").first.click()
    janela = pg.get_by_role("dialog", name="Resumo do ofício")
    expect(janela).to_be_visible()
    expect(janela.locator(".resumo__documentos li").first).to_be_visible()
    _sem_rolagem_lateral(pg)
    pg.keyboard.press("Escape")
    expect(janela).to_be_hidden()
    expect(pg.locator(".registro").first).to_be_visible()

    # Nova busca: sem resultado e de volta.
    busca.fill("zzzz-nada-encontrado")
    expect(pg.get_by_text("Nenhum ofício encontrado")).to_be_visible()
    busca.fill("")
    expect(pg.locator(".registro").first).to_be_visible()

    # Editar um rascunho e salvar.
    pg.goto("/viagens/oficios/?documento=rascunho")
    pg.locator(".registro__link").first.click()  # o título abre a janela de resumo…
    janela = pg.get_by_role("dialog", name="Resumo do ofício")
    janela.get_by_role("link", name="Abrir o ofício").click()  # …e editar é ação explícita
    motivo = pg.get_by_label("Motivo da viagem")
    motivo.fill(f"Reunião regional de alinhamento (teste E2E em {largura}px).")
    pg.get_by_role("button", name=re.compile(r"^Salvar( rascunho)?$")).click()  # "rascunho" some no celular
    expect(pg.locator("[data-status-salvamento]")).to_contain_text("Rascunho salvo às")
    _sem_rolagem_lateral(pg)

    # Sair → login; a entrada automática não volta depois de sair.
    pg.get_by_role("button", name=re.compile("Menu do usuário")).click()
    pg.get_by_role("menuitem", name="Sair").click()
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()
    pg.goto("/viagens/oficios/")
    expect(pg.get_by_role("heading", name="Acesso ao sistema")).to_be_visible()

    assert pg.problemas == []  # type: ignore[attr-defined]
    pg.context.close()
