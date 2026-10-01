"""Fase 12: 360/390/768/1024/1280/1440 — sem rolagem horizontal, sem sobreposição,
sem texto cortado em botões; captura de cada página em cada largura."""

from __future__ import annotations

import pytest

from .conftest import ARTEFATOS, LARGURAS
from .rotas import ROTAS_AUTENTICADAS, resolver

pytestmark = pytest.mark.visual

SOBREPOSICAO_JS = """() => {
  const alvos = [...document.querySelectorAll('a, button, input, select, textarea, [role=button]')]
    .filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !e.closest('[hidden], dialog:not([open]), .sr-only, [inert]'); });
  const problemas = [];
  for (let i = 0; i < alvos.length; i++) {
    const a = alvos[i].getBoundingClientRect();
    for (let j = i + 1; j < alvos.length; j++) {
      if (alvos[i].contains(alvos[j]) || alvos[j].contains(alvos[i])) continue;
      const b = alvos[j].getBoundingClientRect();
      const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (x > 4 && y > 4) problemas.push([alvos[i].outerHTML.slice(0, 80), alvos[j].outerHTML.slice(0, 80)]);
    }
  }
  return problemas.slice(0, 5);
}"""

CORTADO_JS = """() => [...document.querySelectorAll('.botao, .selo, .aba, .lateral__link')]
  .filter(e => e.offsetParent && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).whiteSpace === 'nowrap')
  .map(e => e.textContent.trim().slice(0, 60)).slice(0, 5)"""


@pytest.mark.parametrize("largura", LARGURAS)
@pytest.mark.parametrize("rota", ROTAS_AUTENTICADAS)
def test_layout_em_cada_largura(logado, dados_e2e, rota, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    url = resolver(rota, dados_e2e.ids)
    pg.goto(url, wait_until="networkidle")
    excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    nome = url.strip("/").replace("/", "_").replace("?", "_").replace("=", "-") or "raiz"
    destino = ARTEFATOS / "responsivo" / str(largura) / f"{nome}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(destino), full_page=True)
    assert excesso <= 0, f"{url} @ {largura}px: rolagem horizontal de {excesso}px"
    assert pg.evaluate(SOBREPOSICAO_JS) == [], f"{url} @ {largura}px: elementos sobrepostos"
    assert pg.evaluate(CORTADO_JS) == [], f"{url} @ {largura}px: texto cortado"
    assert pg.erros_console == [], f"{url}: erros no console {pg.erros_console}"
