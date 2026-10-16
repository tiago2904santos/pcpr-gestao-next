// @ts-check
/**
 * Prévia do documento embutida nas folhas da prestação (`iframe[data-previa-documento]`):
 * recarrega depois de cada gravação automática (`pcpr:dados-salvos`, autosave.js) e ao
 * trocar o servidor da prévia (`select[data-previa-servidor]`, que escolhe a URL). A folha
 * dentro do iframe é só leitura — o que muda é o formulário da página.
 */

/** @param {HTMLIFrameElement} quadro */
function recarregar(quadro) {
  const src = quadro.getAttribute("src");
  if (!src) return;
  const url = new URL(src, location.href);
  url.searchParams.set("v", String(Date.now()));
  quadro.src = url.toString();
}

document.addEventListener("pcpr:dados-salvos", () => {
  document.querySelectorAll("iframe[data-previa-documento]").forEach((q) => recarregar(/** @type {HTMLIFrameElement} */ (q)));
});

document.addEventListener("change", (e) => {
  const seletor = /** @type {HTMLSelectElement | null} */ (
    /** @type {Element} */ (e.target).closest("select[data-previa-servidor]"));
  if (!seletor) return;
  const quadro = /** @type {HTMLIFrameElement | null} */ (
    document.getElementById(seletor.dataset.previaServidor || ""));
  if (quadro && seletor.value) quadro.src = seletor.value;
});

export {};
