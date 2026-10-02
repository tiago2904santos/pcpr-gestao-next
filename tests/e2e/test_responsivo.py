"""Fase 12: 360/390/768/1024/1280/1440 — sem rolagem horizontal, sem sobreposição,
sem texto cortado em botões; captura de cada página em cada largura."""

from __future__ import annotations

import pytest

from .conftest import ARTEFATOS, LARGURAS, nome_seguro
from .rotas import ROTAS_AUTENTICADAS, resolver

pytestmark = pytest.mark.visual

SOBREPOSICAO_JS = """() => {
  const alvos = [...document.querySelectorAll('a, button, input, select, textarea, [role=button]')]
    .filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
      if (!(r.width > 1 && r.height > 1) || s.visibility === 'hidden') return false;
      // Conteúdo pulado pelo navegador (gaveta <details> fechada, content-visibility) ainda
      // devolve um retângulo antigo em getBoundingClientRect, mas não é pintado, não recebe
      // clique e não aceita foco — medir isso dava sobreposição que ninguém vê na tela.
      if (!e.checkVisibility()) return false;
      if (e.closest('[hidden], dialog:not([open]), .sr-only, [inert], .barra-acoes, .cabecalho')) return false;
      for (let p = e.parentElement; p; p = p.parentElement) { if (getComputedStyle(p).clip !== 'auto') return false; }
      return true; });
  const problemas = [];
  for (let i = 0; i < alvos.length; i++) {
    const a = alvos[i].getBoundingClientRect();
    for (let j = i + 1; j < alvos.length; j++) {
      if (alvos[i].contains(alvos[j]) || alvos[j].contains(alvos[i])) continue;
      // Botão dentro do próprio campo (calendário/relógio, mostrar senha, limpar): a
      // sobreposição é intencional e o campo reserva o espaço dele no padding-right.
      const DENTRO_DO_CAMPO = '.seletor, .entrada-composta--senha, .entrada-composta--limpavel';
      const seletor = alvos[i].closest(DENTRO_DO_CAMPO);
      if (seletor && seletor === alvos[j].closest(DENTRO_DO_CAMPO)) continue;
      const b = alvos[j].getBoundingClientRect();
      const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (x > 4 && y > 4) problemas.push([alvos[i].outerHTML.slice(0, 80), alvos[j].outerHTML.slice(0, 80)]);
    }
  }
  return problemas.slice(0, 5);
}"""

CULPADOS_JS = """() => { const w = window.innerWidth; const out = [];
  document.querySelectorAll('body *').forEach(e => { const r = e.getBoundingClientRect();
    if (r.right > w + 1 && r.width > 0) { let p = e.parentElement, cortado = false;
      while (p) { const s = getComputedStyle(p); if (['auto','scroll','hidden','clip'].includes(s.overflowX)) { cortado = true; break; } p = p.parentElement; }
      if (!cortado) out.push(e.tagName + '.' + (e.className.baseVal ?? e.className) + ' →' + Math.round(r.right)); } });
  document.querySelectorAll('body *').forEach(e => { const s = getComputedStyle(e);
    if (s.overflowX === 'visible' && e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0 && !['TABLE','TBODY','THEAD','TR','svg','use'].includes(e.tagName))
      out.push('texto vazando: ' + e.tagName + '.' + (e.className.baseVal ?? e.className)); });
  return out.slice(0, 8); }"""

CORTADO_JS = """() => [...document.querySelectorAll('.botao, .selo, .aba, .navegacao__link, .navegacao__seletor, .marca__titulo')]
  .filter(e => e.offsetParent && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).whiteSpace === 'nowrap')
  .map(e => e.textContent.trim().slice(0, 60)).slice(0, 5)"""

# O cabeçalho fica fora do detector geral (é fixo); aqui seus blocos não podem se sobrepor
# (ex.: nome do produto por baixo do selo de ambiente) e a busca não pode virar um toco.
CABECALHO_JS = """() => {
  const blocos = [...document.querySelectorAll('.cabecalho > *, .marca > *')]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 1 && getComputedStyle(e).display !== 'none'; });
  const problemas = [];
  for (let i = 0; i < blocos.length; i++) for (let j = i + 1; j < blocos.length; j++) {
    if (blocos[i].contains(blocos[j]) || blocos[j].contains(blocos[i])) continue;
    const a = blocos[i].getBoundingClientRect(), b = blocos[j].getBoundingClientRect();
    if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
      problemas.push(blocos[i].className + ' × ' + blocos[j].className);
  }
  const texto = document.querySelector('.busca-global__texto');
  if (texto && getComputedStyle(texto).display !== 'none' && texto.getBoundingClientRect().width < 80)
    problemas.push('busca espremida: ' + Math.round(texto.getBoundingClientRect().width) + 'px');
  return problemas;
}"""



@pytest.mark.parametrize("largura", LARGURAS)
@pytest.mark.parametrize("rota", ROTAS_AUTENTICADAS)
def test_layout_em_cada_largura(logado, dados_e2e, rota, largura):
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    url = resolver(rota, dados_e2e.ids)
    pg.goto(url, wait_until="networkidle")
    excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    nome = nome_seguro(url)
    destino = ARTEFATOS / "responsivo" / str(largura) / f"{nome}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(destino), full_page=True)
    assert excesso <= 0, (f"{url} @ {largura}px: rolagem horizontal de {excesso}px "
                          f"{pg.evaluate(CULPADOS_JS)}")
    sobrepostos = pg.evaluate(SOBREPOSICAO_JS)
    assert sobrepostos == [], f"{url} @ {largura}px: elementos sobrepostos {sobrepostos}"
    assert pg.evaluate(CORTADO_JS) == [], f"{url} @ {largura}px: texto cortado"
    assert pg.evaluate(CABECALHO_JS) == [], f"{url} @ {largura}px: cabeçalho {pg.evaluate(CABECALHO_JS)}"
    erros = [e for e in pg.erros_console
             if not ("404" in e and url.startswith("/nao-existe"))]  # 404 é o esperado ali
    assert erros == [], f"{url}: erros no console {erros}"
