// @ts-check
/**
 * Registro expansível (listas): `<button data-expandir aria-expanded="false">` dentro de
 * `.registro` abre/fecha `.registro__extra`. O conteúdo vem por HTMX na primeira abertura
 * (depois, `data-carregado` no registro cancela novas buscas); este módulo cuida
 * do estado visual, do carregamento (aria-busy, erro) e do teclado (Esc fecha e devolve
 * o foco ao botão — sem roubar o Esc dos menus abertos dentro da linha).
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
  const alvo = /** @type {HTMLElement} */ (e.target);
  if (alvo.closest("[role='menu']")) return; // o menu trata o seu próprio Esc
  const registro = /** @type {HTMLElement | null} */ (alvo.closest(".registro--aberto"));
  if (!registro) return;
  const botao = /** @type {HTMLElement | null} */ (registro.querySelector("[data-expandir]"));
  registro.classList.remove("registro--aberto");
  botao?.setAttribute("aria-expanded", "false");
  botao?.focus();
});

// Continuidade espacial com custo mínimo: ao sair da página por um registro, só a placa
// daquele registro mantém o nome de transição (as outras 19 não viram snapshot).
/** @type {Element | null} */
let registroAtivado = null;
document.addEventListener("click", (e) => {
  registroAtivado = /** @type {HTMLElement} */ (e.target).closest(".registro");
}, true);
window.addEventListener("pageswap", (evento) => {
  if (!(/** @type {any} */ (evento)).viewTransition) return;
  document.querySelectorAll(".registro .placa[data-vt]").forEach((placa) => {
    if (!registroAtivado || !registroAtivado.contains(placa)) placa.removeAttribute("data-vt");
  });
});

// Recém-alterado: a linha do registro que acabou de ser salvo acende em dourado — a pessoa
// volta da edição e sabe onde o item está sem procurar.
try {
  const chave = window.sessionStorage.getItem("pcpr-destaque");
  const alvo = chave ? document.querySelector(`.registro[data-destaque="${CSS.escape(chave)}"]`) : null;
  if (chave) window.sessionStorage.removeItem("pcpr-destaque");
  if (alvo) {
    alvo.classList.add("registro--destaque");
    alvo.addEventListener("animationend", () => alvo.classList.remove("registro--destaque"), { once: true });
    const r = alvo.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) alvo.scrollIntoView({ block: "center" });
  }
} catch {
  /* sessionStorage bloqueado: sem destaque */
}

/** @param {Event} evento @returns {HTMLElement | null} */
function extraDe(evento) {
  const e = /** @type {CustomEvent} */ (evento);
  const origem = /** @type {HTMLElement | undefined} */ (e.detail?.elt);
  if (!origem?.hasAttribute("data-expandir")) return null;
  return /** @type {HTMLElement | null} */ (origem.closest(".registro")?.querySelector(".registro__extra"));
}

document.body.addEventListener("htmx:beforeRequest", (evento) => {
  const extra = extraDe(evento);
  if (!extra) return;
  // Já carregado: não busca de novo (sem filtro de evento no hx-trigger — a CSP proíbe eval).
  if (extra.closest(".registro")?.hasAttribute("data-carregado")) {
    evento.preventDefault();
    return;
  }
  extra.setAttribute("aria-busy", "true");
});

document.body.addEventListener("htmx:afterRequest", (evento) => {
  const extra = extraDe(evento);
  if (!extra) return;
  extra.removeAttribute("aria-busy");
  const ok = Boolean(/** @type {CustomEvent} */ (evento).detail?.successful);
  if (ok) {
    extra.closest(".registro")?.setAttribute("data-carregado", "");
    return;
  }
  // Falhou: mensagem no lugar do esqueleto; o próximo clique tenta de novo.
  extra.textContent = "";
  const aviso = document.createElement("p");
  aviso.className = "registro__erro";
  aviso.setAttribute("role", "alert");
  aviso.textContent = "Não foi possível carregar o resumo. Tente de novo.";
  extra.append(aviso);
});
