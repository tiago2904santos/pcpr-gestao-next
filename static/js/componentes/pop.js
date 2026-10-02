// @ts-check
/**
 * Caixa que aparece ao pousar o mouse (ou ao focar) sobre um gatilho — para espiar uma
 * lista curta sem sair da página e sem abrir uma janela. É a caixa de ações: nasce
 * colada ao gatilho e some ao sair dele.
 *
 * Marcação: <button data-pop="<id do painel>"> e <div id="<id>" popover class="pop">.
 * O conteúdo pode vir por HTMX no primeiro pouso (hx-trigger="mouseenter once").
 * Fica na camada de topo (popover), então nenhum recorte da lista a corta.
 */
const ESPERA_SAIDA = 160;
/** @type {Map<HTMLElement, number>} */
const saidas = new Map();

/** @param {HTMLElement} gatilho */
function painelDe(gatilho) {
  return /** @type {HTMLElement & {showPopover?: () => void, hidePopover?: () => void} | null} */ (
    document.getElementById(gatilho.dataset.pop || "")
  );
}

/** @param {HTMLElement} gatilho @param {HTMLElement} painel */
function posicionar(gatilho, painel) {
  const campo = gatilho.getBoundingClientRect();
  const folga = 8;
  painel.style.left = `${Math.max(folga, Math.min(campo.left,
    document.documentElement.clientWidth - painel.offsetWidth - folga))}px`;
  const abaixo = campo.bottom + folga;
  const cabe = abaixo + painel.offsetHeight <= window.innerHeight - folga;
  painel.style.top = cabe
    ? `${abaixo}px`
    : `${Math.max(folga, campo.top - painel.offsetHeight - folga)}px`;
}

/** @param {HTMLElement} gatilho */
function abrir(gatilho) {
  const painel = painelDe(gatilho);
  if (!painel) return;
  window.clearTimeout(saidas.get(painel));
  if (!painel.matches(":popover-open")) {
    painel.showPopover?.();
    gatilho.setAttribute("aria-expanded", "true");
  }
  posicionar(gatilho, painel);
}

/** @param {HTMLElement} gatilho */
function agendarFechar(gatilho) {
  const painel = painelDe(gatilho);
  if (!painel) return;
  window.clearTimeout(saidas.get(painel));
  saidas.set(painel, window.setTimeout(() => {
    // Com o mouse sobre o próprio painel, ele fica: a pessoa está lendo (ou clicando).
    if (painel.matches(":hover") || painel.contains(document.activeElement)) return;
    painel.hidePopover?.();
    gatilho.setAttribute("aria-expanded", "false");
  }, ESPERA_SAIDA));
}

/** @param {Event} e @returns {HTMLElement | null} */
const gatilhoDe = (e) => /** @type {HTMLElement} */ (e.target)?.closest?.("[data-pop]") || null;

document.addEventListener("pointerover", (e) => {
  const gatilho = gatilhoDe(e);
  if (gatilho) abrir(gatilho);
});
document.addEventListener("pointerout", (e) => {
  const gatilho = gatilhoDe(e);
  if (gatilho) agendarFechar(gatilho);
});
document.addEventListener("focusin", (e) => {
  const gatilho = gatilhoDe(e);
  if (gatilho) abrir(gatilho);
});
document.addEventListener("focusout", (e) => {
  const gatilho = gatilhoDe(e);
  if (gatilho) agendarFechar(gatilho);
});
// Clique no gatilho (toque, teclado) alterna, para quem não tem mouse.
document.addEventListener("click", (e) => {
  const gatilho = gatilhoDe(e);
  if (!gatilho) return;
  const painel = painelDe(gatilho);
  if (!painel) return;
  if (painel.matches(":popover-open")) {
    painel.hidePopover?.();
    gatilho.setAttribute("aria-expanded", "false");
  } else {
    abrir(gatilho);
  }
});

export {};
