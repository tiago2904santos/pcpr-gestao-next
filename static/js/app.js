// @ts-check
/**
 * Ponto de entrada do front-end. Sem bundler: módulos ES servidos direto.
 * O que toda tela usa (shell, menus, diálogos, toasts, paleta, ações HTMX) entra sempre, pré-carregado
 * com <link rel="modulepreload"> (templates/base_documento.html). O resto só entra quando a tela tem
 * o elemento que o pede — a tela que precisa pré-carrega os seus no bloco `modulos`.
 */
import "./componentes/shell.js";
import "./componentes/menu.js";
import "./componentes/dialogo.js";
import "./componentes/toasts.js";
import "./componentes/comandos.js";
import "./componentes/acao.js";

/** @type {Array<[string, () => Promise<unknown>]>} */
const sobDemanda = [
  ["pc-combobox", () => import("./componentes/combobox.js")],
  ["pc-abas", () => import("./componentes/abas.js")],
  ["[data-mascara]", () => import("./componentes/mascara.js")],
  ["input[type='search'].entrada, input[data-limpavel]", () => import("./componentes/limpar.js")],
  ["form[data-proteger]", () => import("./componentes/protecao.js")],
  ["form[data-autosave]", () => import("./componentes/autosave.js")],
  [".registro", () => import("./componentes/registro.js")],
  [".documento", () => import("./componentes/guia.js")],
  [".progresso", () => import("./componentes/progresso.js")],
  ["pc-data", () => import("./componentes/seletor-data.js")],
  ["pc-hora", () => import("./componentes/seletor-hora.js")],
  ["pc-select", () => import("./componentes/seletor.js")],
  ["pc-transporte", () => import("./componentes/transporte.js")],
  ["[data-texto-pronto]", () => import("./componentes/texto-pronto.js")],
];
const carregados = new Set();
function carregarSobDemanda() {
  for (const [seletor, carregar] of sobDemanda) {
    if (carregados.has(seletor) || !document.querySelector(seletor)) continue;
    carregados.add(seletor);
    carregar();
  }
}
carregarSobDemanda();
// Fragmentos HTMX podem trazer um componente que a tela ainda não tinha.
document.body.addEventListener("htmx:afterSwap", carregarSobDemanda);

/**
 * Componentes pesados que ficam longe do topo só carregam quando chegam perto da tela
 * (ex.: o editor de documento, 39 KB, no fim da folha do ofício). Sem IntersectionObserver,
 * carregam na hora.
 * @type {Array<[string, () => Promise<unknown>]>}
 */
const quandoVisivel = [
  ["pc-editor-documento", () => import("./componentes/editor-documento.js")],
];
function carregarQuandoVisivel() {
  for (const [seletor, carregar] of quandoVisivel) {
    const alvos = document.querySelectorAll(seletor);
    if (carregados.has(seletor) || !alvos.length) continue;
    carregados.add(seletor);
    if (!("IntersectionObserver" in window)) { carregar(); continue; }
    const observador = new IntersectionObserver((entradas) => {
      if (!entradas.some((e) => e.isIntersecting)) return;
      observador.disconnect();
      carregar();
    }, { rootMargin: "400px 0px" });
    alvos.forEach((alvo) => observador.observe(alvo));
  }
}
carregarQuandoVisivel();
document.body.addEventListener("htmx:afterSwap", carregarQuandoVisivel);

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
