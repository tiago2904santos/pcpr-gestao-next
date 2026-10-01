// @ts-check
/**
 * Proteção contra perda de dados em formulários longos (`<form data-proteger>`).
 *  - Marca o formulário como "sujo" ao editar qualquer campo ligado a ele
 *    (inclusive campos fora do <form> com o atributo `form="id"`);
 *  - mostra o aviso em `[data-status-salvamento]` e pede confirmação ao sair da página;
 *  - Ctrl+S (ou Cmd+S) salva pelo botão padrão do formulário.
 */

/** @param {HTMLFormElement} form */
function proteger(form) {
  let sujo = form.hasAttribute("data-sujo");
  const status = /** @type {HTMLElement | null} */ (document.querySelector("[data-status-salvamento]"));

  const marcar = () => {
    if (sujo) return;
    sujo = true;
    if (status) {
      status.textContent = status.dataset.textoSujo || "Alterações não salvas.";
      status.classList.add("barra-acoes__status--sujo");
    }
  };
  if (sujo && status) status.classList.add("barra-acoes__status--sujo");

  document.addEventListener("input", (e) => {
    const campo = /** @type {HTMLInputElement} */ (e.target);
    if (campo.form === form) marcar();
  });
  document.addEventListener("change", (e) => {
    const campo = /** @type {HTMLInputElement} */ (e.target);
    if (campo.form === form) marcar();
  });
  form.addEventListener("submit", () => {
    sujo = false;
  });
  window.addEventListener("beforeunload", (e) => {
    if (!sujo) return;
    e.preventDefault();
    e.returnValue = "";
  });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      form.requestSubmit();
    }
  });
}

document.querySelectorAll("form[data-proteger]").forEach((f) => proteger(/** @type {HTMLFormElement} */ (f)));

// Campo focado nunca fica atrás da barra de ações fixa (WCAG 2.4.11).
document.addEventListener("focusin", (e) => {
  const barra = document.querySelector(".barra-acoes");
  const alvo = /** @type {HTMLElement} */ (e.target);
  if (!barra || barra.contains(alvo)) return;
  const topoBarra = barra.getBoundingClientRect().top;
  const caixa = alvo.getBoundingClientRect();
  if (caixa.bottom > topoBarra - 8) {
    window.scrollBy({ top: caixa.bottom - topoBarra + 24, behavior: "instant" });
  }
});
