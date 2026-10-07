// @ts-check
/**
 * Barra de filtros das listas (arquétipo LIST), carregado sob demanda:
 *
 * 1. Gaveta `details.filtros__mais` (D6): fecha com Esc, com clique fora (inclusive no véu
 *    da folha inferior do celular) e com o botão `[data-fechar-filtros]`; Esc e "Fechar"
 *    devolvem o foco ao botão da gaveta. Continua um <details>: sem JavaScript, abre e
 *    fecha no próprio botão.
 * 2. Erro da busca ao vivo (LP-23): sem rede ou com erro do servidor, o aviso
 *    `[data-erro-lista]` (componentes/erro_lista.html) aparece NO LUGAR de #resultados —
 *    a lista velha não fica fingindo ser o resultado novo — e "Tentar de novo" refaz o
 *    mesmo pedido (o formulário ou o link que o disparou).
 * 3. Escopo da busca (refino): digitar outro termo volta à busca ampla.
 */

/** @param {HTMLDetailsElement} gaveta @param {boolean} devolverFoco */
function fechar(gaveta, devolverFoco) {
  if (!gaveta.open) return;
  gaveta.open = false;
  const resumo = gaveta.querySelector("summary");
  const ativo = document.activeElement;
  const focoPerdido = !ativo || ativo === document.body || gaveta.contains(ativo);
  if (resumo && (devolverFoco || focoPerdido)) resumo.focus({ preventScroll: true });
}

/** @returns {HTMLDetailsElement[]} */
function gavetasAbertas() {
  return /** @type {HTMLDetailsElement[]} */ (
    Array.from(document.querySelectorAll("details.filtros__mais[open]")));
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || e.defaultPrevented) return;
  const gaveta = gavetasAbertas()[0];
  if (!gaveta) return;
  // Um diálogo aberto por cima (ex.: o resumo) tem prioridade sobre a gaveta.
  if (document.querySelector("dialog[open]")) return;
  e.preventDefault();
  fechar(gaveta, true);
});

// Clique fora: o véu do celular é um ::before do próprio <details>, então o clique nele
// chega com o alvo = <details> (e não um filho).
document.addEventListener("pointerdown", (e) => {
  const alvo = /** @type {Node} */ (e.target);
  for (const gaveta of gavetasAbertas()) {
    if (alvo === gaveta || !gaveta.contains(alvo)) {
      // Fecha depois do clique: o foco vai para onde a pessoa clicou (um link, um campo).
      window.setTimeout(() => fechar(gaveta, false), 0);
    }
  }
});

// "Fechar" só existe com JavaScript (sem ele, a gaveta fecha no próprio botão).
document.querySelectorAll("[data-fechar-filtros][hidden]").forEach((b) => b.removeAttribute("hidden"));

document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement} */ (e.target).closest("[data-fechar-filtros]");
  const gaveta = /** @type {HTMLDetailsElement | null} */ (botao?.closest("details") ?? null);
  if (gaveta) fechar(gaveta, true);
});

// Abrir a gaveta no celular (folha inferior) leva o foco ao primeiro campo: a folha cobre
// a lista, e o leitor de tela precisa saber que entrou nela.
document.addEventListener("toggle", (e) => {
  const gaveta = /** @type {HTMLElement} */ (e.target);
  if (!(gaveta instanceof HTMLDetailsElement) || !gaveta.matches(".filtros__mais")) return;
  if (!gaveta.open || !window.matchMedia("(max-width: 767.98px)").matches) return;
  const primeiro = /** @type {HTMLElement | null} */ (
    gaveta.querySelector(".filtros__avancados select, .filtros__avancados input:not([type=hidden])"));
  primeiro?.focus({ preventScroll: true });
}, true);

// ------------------------------------------------------------------ erro da busca ao vivo
/** @type {HTMLElement | null} */
let quemPediu = null;

/** @param {Event} e */
function alvoDaLista(e) {
  const detalhe = /** @type {any} */ (e).detail || {};
  const alvo = /** @type {HTMLElement | null} */ (detalhe.target || null);
  return alvo && alvo.id === "resultados" ? alvo : null;
}

/** @param {HTMLElement} resultados @param {boolean} comErro @param {string} [texto] */
function mostrarErro(resultados, comErro, texto) {
  const caixa = resultados.parentElement?.querySelector("[data-erro-lista]");
  if (!(caixa instanceof HTMLElement)) return;
  if (comErro) {
    const detalhe = caixa.querySelector("[data-erro-detalhe]");
    if (detalhe && texto) detalhe.textContent = texto;
  }
  caixa.hidden = !comErro;
  resultados.hidden = comErro;
}

/** @param {Event} e @param {string} texto */
function falhou(e, texto) {
  const resultados = alvoDaLista(e);
  if (!resultados) return;
  quemPediu = /** @type {any} */ (e).detail?.elt || null;
  mostrarErro(resultados, true, texto);
}

document.body.addEventListener("htmx:sendError", (e) => falhou(
  e, "Sem conexão com o servidor. Confira a rede e tente de novo — nada do que você filtrou se perdeu."));
document.body.addEventListener("htmx:responseError", (e) => falhou(
  e, "O servidor não conseguiu responder agora. Tente de novo em instantes — nada do que você filtrou se perdeu."));
document.body.addEventListener("htmx:afterSwap", (e) => {
  const resultados = document.getElementById("resultados");
  if (resultados && alvoDaLista(e)) mostrarErro(resultados, false);
});

document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement} */ (e.target).closest("[data-tentar-de-novo]");
  if (!botao) return;
  const origem = quemPediu && quemPediu.isConnected ? quemPediu : null;
  if (origem instanceof HTMLFormElement) origem.requestSubmit();
  else if (origem) origem.click();
  else window.location.reload();
});

// ------------------------------------------------------------------ endereço limpo
// A busca ao vivo põe o pedido na barra de endereço (hx-push-url): sem os campos vazios,
// o link que a pessoa copia diz só o que está filtrando ("?q=arapongas&documento=rascunho"
// em vez de onze "campo=" vazios). O servidor trata ausente e vazio do mesmo jeito.
document.body.addEventListener("htmx:configRequest", (e) => {
  const detalhe = /** @type {any} */ (e).detail || {};
  const form = detalhe.elt;
  const dados = /** @type {FormData | undefined} */ (detalhe.formData);
  if (!(form instanceof HTMLFormElement) || form.getAttribute("role") !== "search" || !dados) return;
  for (const chave of new Set(Array.from(dados.keys()))) {
    if (dados.getAll(chave).every((valor) => valor === "")) dados.delete(chave);
  }
});

// ------------------------------------------------------------------ escopo da busca
document.addEventListener("input", (e) => {
  const campo = /** @type {HTMLElement} */ (e.target);
  if (!(campo instanceof HTMLInputElement) || campo.type !== "search") return;
  const escopo = campo.form?.querySelector("[data-escopo-da-busca]");
  if (escopo instanceof HTMLInputElement) escopo.value = "";
});

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
