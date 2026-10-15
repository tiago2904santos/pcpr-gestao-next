// @ts-check
/**
 * Visualizador dos documentos da viagem (viagem/_visualizador.html). Os cartões da trilha
 * (`a[data-visualizar]`) abrem o modal em vez de navegar — Ctrl/⌘/clique do meio continuam
 * abrindo a folha de edição, e sem JavaScript o link leva até ela.
 *
 * - Documento pronto (`data-paginas`, as folhas em JSON): a folha ao lado do resumo; no
 *   celular, Documento × Resumo. Mais de uma página (ofício e justificativa, os termos):
 *   a escolha da página.
 * - Não pronto, com pendência ou roteiro: só o resumo (o fragmento das listas, por HTMX, com
 *   as ações no rodapé).
 * - Setas (e ← →) passam entre os documentos do mesmo tipo (`data-grupo`).
 */

const A4_LARGURA_PX = (210 / 25.4) * 96;  // a folha tem a largura do A4, com a mesa em volta
const MARGEM_DA_MESA_PX = 48;

/** @param {HTMLElement} dialogo */
function ligar(dialogo) {
  if (dialogo.dataset.pronto) return;
  dialogo.dataset.pronto = "1";
  const d = /** @type {HTMLDialogElement} */ (dialogo);
  const $ = (/** @type {string} */ s) => /** @type {HTMLElement} */ (d.querySelector(s));
  const titulo = $("[data-v-titulo]");
  const tipo = $("[data-v-tipo]");
  const navegacao = $("[data-v-navegacao]");
  const posicao = $("[data-v-posicao]");
  const anterior = /** @type {HTMLButtonElement} */ ($("[data-v-anterior]"));
  const proximo = /** @type {HTMLButtonElement} */ ($("[data-v-proximo]"));
  const caixaPagina = $("[data-v-pagina]");
  const paginas = /** @type {HTMLSelectElement} */ ($("[data-v-paginas]"));
  const modos = $("[data-v-modos]");
  const documento = $("[data-v-documento]");
  const folha = /** @type {HTMLIFrameElement} */ ($("[data-v-folha]"));
  const resumo = $("[data-v-resumo]");
  const carregando = resumo.innerHTML;

  /** @type {HTMLAnchorElement[]} */
  let grupo = [];
  let indice = 0;

  const escala = () => {
    const doc = folha.contentDocument;
    if (!doc?.documentElement || !documento.clientWidth) return;
    const fator = Math.min(1, (documento.clientWidth - 2) / (A4_LARGURA_PX + MARGEM_DA_MESA_PX));
    doc.documentElement.style.setProperty("zoom", String(fator));
  };
  folha.addEventListener("load", escala);
  new ResizeObserver(escala).observe(documento);

  /** @param {"documento" | "resumo"} modo */
  const mostrarModo = (modo) => {
    d.dataset.modo = modo;
    modos.querySelectorAll("[data-v-modo]").forEach((b) =>
      b.setAttribute("aria-pressed", String(/** @type {HTMLElement} */ (b).dataset.vModo === modo)));
  };

  /** @param {HTMLAnchorElement} cartao */
  const mostrar = (cartao) => {
    const dados = cartao.dataset;
    tipo.textContent = dados.tipo || "";
    titulo.textContent = dados.titulo || "Documento";
    navegacao.hidden = grupo.length < 2;
    posicao.textContent = `${indice + 1} de ${grupo.length}`;
    anterior.disabled = indice === 0;
    proximo.disabled = indice === grupo.length - 1;

    /** @type {{rotulo: string, url: string}[]} */
    let lista = [];
    try { lista = dados.paginas ? JSON.parse(dados.paginas) : []; } catch { lista = []; }
    const temDocumento = lista.length > 0;
    d.classList.toggle("visualizador--com-documento", temDocumento);
    documento.hidden = !temDocumento;
    modos.hidden = !temDocumento;
    caixaPagina.hidden = lista.length < 2;
    paginas.replaceChildren(...lista.map((p) => new Option(p.rotulo, p.url)));
    if (temDocumento) {
      folha.title = `${dados.titulo}: documento`;
      folha.src = lista[0].url;
      mostrarModo("documento");
    } else {
      folha.removeAttribute("src");
      mostrarModo("resumo");
    }

    resumo.innerHTML = carregando;
    const htmx = /** @type {any} */ (window).htmx;
    if (htmx && dados.resumo) {
      htmx.ajax("GET", dados.resumo, { target: resumo, swap: "innerHTML" });
    }
  };

  /** @param {number} novo */
  const ir = (novo) => {
    if (novo < 0 || novo >= grupo.length || novo === indice) return;
    indice = novo;
    mostrar(grupo[indice]);
  };

  anterior.addEventListener("click", () => ir(indice - 1));
  proximo.addEventListener("click", () => ir(indice + 1));
  paginas.addEventListener("change", () => { folha.src = paginas.value; });
  modos.addEventListener("click", (e) => {
    const botao = /** @type {HTMLElement | null} */ (/** @type {Element} */ (e.target).closest("[data-v-modo]"));
    if (botao) mostrarModo(/** @type {"documento" | "resumo"} */ (botao.dataset.vModo));
  });
  d.addEventListener("keydown", (e) => {
    const alvo = /** @type {Element} */ (e.target);
    if (alvo.closest("input, textarea, select, [contenteditable]")) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); ir(indice - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); ir(indice + 1); }
  });
  d.addEventListener("close", () => {
    folha.removeAttribute("src");
    grupo[indice]?.focus();
  });

  document.addEventListener("click", (e) => {
    const cartao = /** @type {HTMLAnchorElement | null} */ (
      /** @type {Element} */ (e.target).closest("a[data-visualizar]"));
    if (!cartao || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    grupo = /** @type {HTMLAnchorElement[]} */ (Array.from(document.querySelectorAll(
      `a[data-visualizar][data-grupo="${cartao.dataset.grupo}"]`)));
    indice = Math.max(0, grupo.indexOf(cartao));
    mostrar(cartao);
    if (!d.open) d.showModal();
  });
}

document.querySelectorAll("[data-visualizador]").forEach((d) => ligar(/** @type {HTMLElement} */ (d)));

export {};
