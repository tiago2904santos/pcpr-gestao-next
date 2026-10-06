// @ts-check
/**
 * Abas que rolam de lado (filtros de lista em telas estreitas, LP-11):
 * - marcam em `data-rola` as bordas que escondem abas ("inicio", "fim") — o CSS esmaece
 *   essa borda, o indício de que há mais para o lado;
 * - trazem a aba ativa para a vista ao carregar (antes "Cancelados" ou "Arquivados" ativa
 *   podia ficar fora da tela, sem nenhum sinal).
 * Vale para `nav.abas` (links) e para o `tablist` do <pc-abas>; as abas trocadas pelo HTMX
 * (busca ao vivo) são preparadas de novo.
 */

/** @param {HTMLElement} abas */
function medir(abas) {
  const resto = abas.scrollWidth - abas.clientWidth - abas.scrollLeft;
  const bordas = [abas.scrollLeft > 1 ? "inicio" : "", resto > 1 ? "fim" : ""].filter(Boolean);
  if (bordas.length) abas.dataset.rola = bordas.join(" ");
  else delete abas.dataset.rola;
}

/** @param {HTMLElement} abas */
function centralizarAtiva(abas) {
  const ativa = abas.querySelector("[aria-current='page'], [aria-selected='true']");
  if (!(ativa instanceof HTMLElement) || abas.scrollWidth <= abas.clientWidth) return;
  const caixa = abas.getBoundingClientRect();
  const aba = ativa.getBoundingClientRect();
  const fora = aba.left < caixa.left || aba.right > caixa.right;
  if (!fora) return;
  abas.scrollLeft += aba.left - caixa.left - (caixa.width - aba.width) / 2;
}

/** @param {HTMLElement} abas */
function preparar(abas) {
  if (abas.dataset.rolaPronta) {
    medir(abas);
    return;
  }
  abas.dataset.rolaPronta = "1";
  centralizarAtiva(abas);
  medir(abas);
  abas.addEventListener("scroll", () => medir(abas), { passive: true });
  new ResizeObserver(() => medir(abas)).observe(abas);
}

function prepararTodas() {
  document.querySelectorAll(".abas").forEach((abas) => {
    if (abas instanceof HTMLElement) preparar(abas);
  });
}

prepararTodas();
document.body.addEventListener("htmx:afterSettle", prepararTodas);

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
