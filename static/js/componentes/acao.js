// @ts-check
/**
 * Linguagem de ação dos botões: ocioso → processando → concluído / recusado.
 *
 * Para requisições HTMX disparadas por um botão (ou pelo formulário que ele envia),
 * o botão recebe `aria-busy` enquanto a requisição corre e, ao terminar:
 *  - sucesso → `data-estado="concluido"` por um instante (ícone carimba, fica verde);
 *  - erro    → `data-estado="erro"` (balança uma vez).
 * Rótulos alternativos opcionais: `data-rotulo-processando`, `data-rotulo-concluido`.
 * Nada disso é necessário para o botão funcionar: é feedback, não comportamento.
 */

const DURACAO_CONCLUIDO = 1600;

/** @param {Event} evento @returns {HTMLButtonElement | null} */
function botaoDe(evento) {
  const e = /** @type {CustomEvent} */ (evento);
  const origem = /** @type {HTMLElement | undefined} */ (e.detail?.elt);
  if (!origem) return null;
  if (origem instanceof HTMLButtonElement) return origem;
  const submissor = /** @type {HTMLButtonElement | null | undefined} */ (e.detail?.requestConfig?.triggeringEvent?.submitter);
  if (submissor) return submissor;
  return /** @type {HTMLButtonElement | null} */ (origem.querySelector("button[type=submit]"));
}

/** @param {HTMLButtonElement} b @param {string} chave */
function trocarRotulo(b, chave) {
  const texto = b.dataset[chave];
  if (!texto) return;
  const alvo = /** @type {HTMLElement | null} */ (b.querySelector("span:not(.sr-only)")) || b;
  if (!b.dataset.rotuloOriginal) b.dataset.rotuloOriginal = alvo.textContent || "";
  alvo.textContent = texto;
}

/** @param {HTMLButtonElement} b */
function restaurarRotulo(b) {
  const original = b.dataset.rotuloOriginal;
  if (original === undefined) return;
  const alvo = /** @type {HTMLElement | null} */ (b.querySelector("span:not(.sr-only)")) || b;
  alvo.textContent = original;
  delete b.dataset.rotuloOriginal;
}

document.body.addEventListener("htmx:beforeRequest", (evento) => {
  const b = botaoDe(evento);
  if (!b) return;
  b.setAttribute("aria-busy", "true");
  b.removeAttribute("data-estado");
  trocarRotulo(b, "rotuloProcessando");
});

document.body.addEventListener("htmx:afterRequest", (evento) => {
  const b = botaoDe(evento);
  if (!b) return;
  const e = /** @type {CustomEvent} */ (evento);
  b.removeAttribute("aria-busy");
  if (!b.isConnected) return; // o fragmento trocado levou o botão junto
  const ok = Boolean(e.detail?.successful);
  if (ok) {
    trocarRotulo(b, "rotuloConcluido");
    b.dataset.estado = "concluido";
    window.setTimeout(() => {
      if (b.dataset.estado === "concluido") {
        delete b.dataset.estado;
        restaurarRotulo(b);
      }
    }, DURACAO_CONCLUIDO);
  } else {
    restaurarRotulo(b);
    b.dataset.estado = "erro";
    b.addEventListener("animationend", () => delete b.dataset.estado, { once: true });
  }
});

// Formulário comum recusado pelo navegador (campo required vazio): o botão balança.
document.addEventListener("invalid", (e) => {
  const campo = /** @type {HTMLElement} */ (e.target);
  const form = /** @type {HTMLFormElement | null} */ (campo.closest("form"));
  const b = /** @type {HTMLButtonElement | null} */ (form?.querySelector("button[type=submit]:not(.sr-only)"));
  if (b) {
    b.dataset.estado = "erro";
    b.addEventListener("animationend", () => delete b.dataset.estado, { once: true });
  }
}, true);
