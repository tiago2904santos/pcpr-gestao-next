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
 * 4. Dica curta (`data-dica-curta="a|b"`): quando a caixa da busca fica estreita (768–900px,
 *    a busca divide a linha com Documento e Filtros; o celular), o texto de exemplo cortado
 *    ("Número, protocol") dá lugar à primeira versão curta que cabe (QA Lote 2, M-R4).
 */

/** @param {HTMLDetailsElement} gaveta @param {boolean} devolverFoco */
function fechar(gaveta, devolverFoco) {
  if (!gaveta.open) return;
  desfazerModal(gaveta); // o botão da gaveta precisa sair do inert antes de receber o foco
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

// ------------------------------------------------------------------ folha modal (celular)
// No celular a gaveta é uma folha inferior sobre um véu: modal de verdade (QA Lote 2, I1).
// O resto da página fica `inert` (nem foco nem toque por trás), a página não rola por
// baixo, Tab e Shift+Tab ciclam dentro da folha, o foco começa no 1º controle visível e
// os painéis dos campos (calendário, listas) sobem para a camada de topo
// (`data-camada-topo`, painel-flutuante.js) em vez de serem recortados pela folha.
// No desktop a gaveta continua um painel de divulgação não modal: a lista atrás muda ao
// vivo enquanto se filtra, e as outras listas (Coffee, Eventos…) não mudam de comportamento.
const CELULAR = window.matchMedia("(max-width: 767.98px)");
/** @type {HTMLElement[]} */
let inertes = [];

/** @param {HTMLElement} raiz */
function focaveis(raiz) {
  const candidatos = raiz.querySelectorAll(
    "a[href], button, input:not([type=hidden]), select, textarea, [tabindex]");
  return /** @type {HTMLElement[]} */ (Array.from(candidatos)).filter((el) =>
    el.tabIndex >= 0 && !(/** @type {any} */ (el).disabled) && !el.closest("[hidden]")
    && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden");
}

/** @param {HTMLDetailsElement} gaveta */
function folhaDe(gaveta) {
  return /** @type {HTMLElement | null} */ (gaveta.querySelector(".filtros__avancados--rodape"));
}

/** @param {HTMLDetailsElement} gaveta */
function tornarModal(gaveta) {
  const folha = folhaDe(gaveta);
  if (!folha || folha.dataset.modal) return;
  folha.dataset.modal = "1";
  folha.dataset.camadaTopo = "";
  folha.setAttribute("role", "dialog");
  folha.setAttribute("aria-modal", "true");
  const titulo = folha.querySelector(".filtros__gaveta-titulo");
  if (titulo?.id) folha.setAttribute("aria-labelledby", titulo.id);
  // Tudo o que não é a gaveta (subindo até o <body>) fica inerte; o botão da gaveta, sob o
  // véu, também.
  for (let no = /** @type {HTMLElement} */ (gaveta); no.parentElement && no !== document.body;
    no = no.parentElement) {
    for (const irmao of Array.from(no.parentElement.children)) {
      if (irmao !== no && irmao instanceof HTMLElement && !irmao.inert) {
        irmao.inert = true;
        inertes.push(irmao);
      }
    }
  }
  const resumo = gaveta.querySelector("summary");
  if (resumo && !resumo.inert) { resumo.inert = true; inertes.push(resumo); }
  document.documentElement.classList.add("rolagem-presa");
  focaveis(folha)[0]?.focus({ preventScroll: true });
}

/** @param {HTMLDetailsElement} gaveta */
function desfazerModal(gaveta) {
  const folha = folhaDe(gaveta);
  inertes.forEach((el) => { el.inert = false; });
  inertes = [];
  document.documentElement.classList.remove("rolagem-presa");
  if (!folha || !folha.dataset.modal) return;
  delete folha.dataset.modal;
  delete folha.dataset.camadaTopo;
  folha.setAttribute("role", "group");
  folha.removeAttribute("aria-modal");
  folha.removeAttribute("aria-labelledby");
}

document.addEventListener("toggle", (e) => {
  const gaveta = /** @type {HTMLElement} */ (e.target);
  if (!(gaveta instanceof HTMLDetailsElement) || !gaveta.matches(".filtros__mais")) return;
  if (gaveta.open && CELULAR.matches) tornarModal(gaveta);
  else desfazerModal(gaveta);
}, true);

// Girou o aparelho / alargou a janela com a folha aberta: deixa de ser folha.
CELULAR.addEventListener("change", () => {
  gavetasAbertas().forEach((g) => (CELULAR.matches ? tornarModal(g) : desfazerModal(g)));
});

// Tab e Shift+Tab ciclam dentro da folha.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Tab") return;
  const folha = /** @type {HTMLElement | null} */ (document.querySelector("[data-modal].filtros__avancados"));
  if (!folha) return;
  const lista = focaveis(folha);
  if (!lista.length) return;
  const primeiro = lista[0];
  const ultimo = lista[lista.length - 1];
  const ativo = document.activeElement;
  if (e.shiftKey && (ativo === primeiro || !folha.contains(ativo))) {
    e.preventDefault();
    ultimo.focus();
  } else if (!e.shiftKey && (ativo === ultimo || !folha.contains(ativo))) {
    e.preventDefault();
    primeiro.focus();
  }
});

// ------------------------------------------------------------------ erro da busca ao vivo
/** @type {HTMLElement | null} */
let quemPediu = null;
let focarResultados = false;

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
  if (!resultados || !alvoDaLista(e)) return;
  mostrarErro(resultados, false);
  if (!focarResultados) return;
  // "Tentar de novo" sumiu com o aviso: o foco vai ao título dos resultados (o leitor de
  // tela anuncia "Resultados para … : N ofícios"), nunca ao <body> (QA Lote 2, I2).
  focarResultados = false;
  const titulo = /** @type {HTMLElement} */ (document.getElementById("titulo-resultados") || resultados);
  titulo.tabIndex = -1;
  titulo.focus({ preventScroll: false });
});

document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement} */ (e.target).closest("[data-tentar-de-novo]");
  if (!botao) return;
  const origem = quemPediu && quemPediu.isConnected ? quemPediu : null;
  focarResultados = true;
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
// 4. Dica curta: troca o placeholder pela versão curta quando a longa não cabe na caixa.
document.querySelectorAll("input[data-dica-curta]").forEach((el) => {
  const campo = /** @type {HTMLInputElement} */ (el);
  // Da mais longa à mais curta ("a|b|c"): vale a primeira que cabe; nenhuma cabe, a última.
  const dicas = [campo.placeholder, ...(campo.dataset.dicaCurta || "").split("|").filter(Boolean)];
  const regua = document.createElement("canvas").getContext("2d");
  const medir = () => {
    if (!regua) return;
    const estilo = getComputedStyle(campo);
    regua.font = `${estilo.fontWeight} ${estilo.fontSize} ${estilo.fontFamily}`;
    const util = campo.clientWidth - parseFloat(estilo.paddingLeft) - parseFloat(estilo.paddingRight);
    campo.placeholder = dicas.find((d) => regua.measureText(d).width <= util) || dicas[dicas.length - 1];
  };
  new ResizeObserver(medir).observe(campo);
});

export {};
