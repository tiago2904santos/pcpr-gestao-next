// @ts-check
/**
 * Registro expansível (listas): `<button data-expandir aria-expanded="false">` dentro de
 * `.registro` abre/fecha `.registro__extra`. O conteúdo vem por HTMX na primeira abertura
 * (`hx-trigger="click once"` no próprio botão); este módulo só cuida do estado visual
 * e do teclado (Esc fecha e devolve o foco ao botão).
 */
document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (e.target).closest("[data-expandir]")
  );
  if (!botao) return;
  const registro = botao.closest(".registro");
  if (!registro) return;
  const aberto = botao.getAttribute("aria-expanded") === "true";
  botao.setAttribute("aria-expanded", String(!aberto));
  registro.classList.toggle("registro--aberto", !aberto);
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const registro = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (e.target).closest(".registro--aberto")
  );
  if (!registro) return;
  const botao = /** @type {HTMLElement | null} */ (registro.querySelector("[data-expandir]"));
  registro.classList.remove("registro--aberto");
  botao?.setAttribute("aria-expanded", "false");
  botao?.focus();
});
