// @ts-check
/**
 * Número com − e + (`.passos` com `[data-passo]`): cada clique soma o passo ao campo,
 * dentro do min/max dele, e avisa o formulário (autosave) como se a pessoa tivesse
 * digitado. Delegado no documento: vale para linhas acrescentadas depois (o efetivo do plano).
 */

document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest(".passos [data-passo]"));
  if (!botao) return;
  const campo = /** @type {HTMLInputElement | null} */ (
    botao.closest(".passos")?.querySelector("input"));
  if (!campo) return;
  const passo = Number(botao.dataset.passo || 0);
  const minimo = campo.min === "" ? -Infinity : Number(campo.min);
  const maximo = campo.max === "" ? Infinity : Number(campo.max);
  const atual = Number(campo.value || campo.dataset.padrao || 0);
  const novo = Math.min(maximo, Math.max(minimo, atual + passo));
  if (novo === atual && campo.value !== "") return;
  campo.value = String(novo);
  campo.dispatchEvent(new Event("input", { bubbles: true }));
  campo.dispatchEvent(new Event("change", { bubbles: true }));
});

export {};
