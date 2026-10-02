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
import "./componentes/protecao.js";
import "./componentes/acao.js";
import "./componentes/registro.js";
import "./componentes/progresso.js";
import "./componentes/seletor-data.js";
import "./componentes/seletor-hora.js";
import "./componentes/seletor.js";

// Com JavaScript, o que só serve sem ele some (ex.: "Aplicar" numa busca que já é ao vivo).
document.querySelectorAll("[data-so-sem-js]").forEach((e) => { /** @type {HTMLElement} */ (e).hidden = true; });

// Campo de senha: mostrar/ocultar (componentes/campo_senha.html).
document.querySelectorAll("[data-alternar-senha]").forEach((b) => b.removeAttribute("hidden"));
document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("[data-alternar-senha]")
  );
  if (!botao) return;
  const campo = /** @type {HTMLInputElement | null} */ (
    document.getElementById(botao.getAttribute("aria-controls") || "")
  );
  if (!campo) return;
  const mostrar = campo.type === "password";
  campo.type = mostrar ? "text" : "password";
  botao.setAttribute("aria-pressed", String(mostrar));
  const rotulo = botao.querySelector(".sr-only");
  if (rotulo) rotulo.textContent = mostrar ? "Ocultar senha" : "Mostrar senha";
  campo.focus({ preventScroll: true });
});

// Ao salvar um registro, a lista de onde se veio acende a linha dele (registro.js).
document.addEventListener("submit", (evento) => {
  const form = /** @type {HTMLFormElement} */ (evento.target);
  const chave = form.dataset.destaque;
  if (!chave || evento.defaultPrevented) return;
  try {
    window.sessionStorage.setItem("pcpr-destaque", chave);
  } catch {
    /* armazenamento indisponível: só não há destaque */
  }
});

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
