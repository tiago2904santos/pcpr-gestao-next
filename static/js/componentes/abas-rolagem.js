// @ts-check
/**
 * Abas que rolam de lado (filtros de lista em telas estreitas, LP-11):
 * - marcam em `data-rola` as bordas que escondem abas ("inicio", "fim") — o CSS esmaece
 *   essa borda, o indício de que há mais para o lado;
 * - trazem a aba ativa para a vista ao carregar (antes "Cancelados" ou "Arquivados" ativa
 *   podia ficar fora da tela, sem nenhum sinal).
 * Vale para `nav.abas` (links), para o `tablist` do <pc-abas> e para qualquer trilho marcado
 * com `data-rola-lado` (ex.: o segmentado "Documento" da lista de ofícios no celular); as
 * abas trocadas pelo HTMX (busca ao vivo) são preparadas de novo.
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
  const ativa = abas.querySelector("[aria-current='page'], [aria-selected='true'], :checked + label");
  if (!(ativa instanceof HTMLElement) || abas.scrollWidth <= abas.clientWidth) return;
  const caixa = abas.getBoundingClientRect();
  const aba = ativa.getBoundingClientRect();
  const fora = aba.left < caixa.left || aba.right > caixa.right;
  if (!fora) return;
  abas.scrollLeft += aba.left - caixa.left - (caixa.width - aba.width) / 2;
}

/**
 * Quem chega pelo Tab a um item meio escondido na borda esmaecida o vê inteiro, com folga
 * do esmaecido (o navegador só rola o "mínimo": o anel de foco ficava sob a máscara — ex.:
 * o × de uma ficha a 390px, a lista de módulos a 768px).
 * @param {HTMLElement} abas @param {FocusEvent} e
 */
function mostrarFocado(abas, e) {
  const alvo = e.target;
  if (!(alvo instanceof HTMLElement) || abas.scrollWidth <= abas.clientWidth) return;
  const folga = 40; // um pouco mais que o esmaecido (2–2,5rem)
  const caixa = abas.getBoundingClientRect();
  const item = alvo.getBoundingClientRect();
  if (item.left < caixa.left + folga) abas.scrollLeft -= caixa.left + folga - item.left;
  else if (item.right > caixa.right - folga) abas.scrollLeft += item.right - (caixa.right - folga);
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
  abas.addEventListener("focusin", (e) => mostrarFocado(abas, e));
  new ResizeObserver(() => medir(abas)).observe(abas);
}

function prepararTodas() {
  document.querySelectorAll(".abas, [data-rola-lado]").forEach((abas) => {
    if (abas instanceof HTMLElement) preparar(abas);
  });
}

prepararTodas();
document.body.addEventListener("htmx:afterSettle", prepararTodas);

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
