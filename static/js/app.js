// @ts-check
/**
 * Ponto de entrada do front-end. Sem bundler: módulos ES servidos direto,
 * pré-carregados com <link rel="modulepreload"> (ver templates/base.html).
 */
import "./componentes/shell.js";
import "./componentes/menu.js";
import "./componentes/dialogo.js";
import "./componentes/toasts.js";
import "./componentes/combobox.js";
import "./componentes/comandos.js";
import "./componentes/abas.js";
import "./componentes/mascara.js";

// HTMX: envia o token CSRF em toda requisição e respeita prefers-reduced-motion.
document.body.addEventListener("htmx:configRequest", (evento) => {
  const e = /** @type {CustomEvent} */ (evento);
  const token = document.querySelector("meta[name='csrf-token']")?.getAttribute("content");
  if (token) e.detail.headers["X-CSRFToken"] = token;
});

// Formulários: evita duplo envio e mostra "carregando" no botão acionado.
document.addEventListener("submit", (evento) => {
  if (evento.defaultPrevented) return;
  const botao = /** @type {HTMLButtonElement | null} */ (
    /** @type {SubmitEvent} */ (evento).submitter
  );
  if (botao && !botao.hasAttribute("formnovalidate")) {
    window.setTimeout(() => botao.setAttribute("aria-busy", "true"), 0);
  }
});

// Voltar pelo histórico restaura o botão (bfcache).
window.addEventListener("pageshow", () => {
  document.querySelectorAll("[aria-busy='true']").forEach((b) => b.removeAttribute("aria-busy"));
});
