// @ts-check
/**
 * [data-esvaziar="<id do campo>"] — esvazia o campo e avisa o formulário (ex.: "Voltar ao
 * texto automático" nos textos do plano de trabalho: vazio, o automático volta a valer na
 * próxima gravação). Sem JavaScript, apagar o texto à mão faz o mesmo.
 */

document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement} */ (evento.target).closest("[data-esvaziar]");
  if (!botao) return;
  const campo = /** @type {HTMLTextAreaElement | HTMLInputElement | null} */ (
    document.getElementById(/** @type {HTMLElement} */ (botao).dataset.esvaziar || ""));
  if (!campo) return;
  campo.value = "";
  campo.dispatchEvent(new Event("input", { bubbles: true }));
  campo.focus();
});

export {};
