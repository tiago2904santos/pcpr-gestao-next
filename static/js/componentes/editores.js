// @ts-check
/**
 * Vários editores num bloco só (`[data-editores]` — o termo: uma página por documento).
 *
 *  - uma barra de ferramentas para o bloco: a do editor ativo (`editor--ativo`); as outras
 *    ficam escondidas na mesma casa da grade (editor.css). Ativo é a página onde está o
 *    cursor — ou, rolando, a que está na tela;
 *  - o índice das páginas, à esquerda (no topo, em tela estreita), mostra a miniatura de
 *    cada folha, como num leitor de PDF: leva direto a cada uma e marca onde se está. A
 *    miniatura é a própria folha (a mesma URL do editor), em escala, refeita quando aquela
 *    página grava (`pc-editor:gravado`) ou quando um texto é aplicado em todas.
 * Cada editor continua com a própria gravação e o próprio histórico (editor-documento.js).
 */

const A4_LARGURA_PX = (210 / 25.4) * 96;  // 210 mm em px CSS

/**
 * Põe a folha da miniatura em escala: só o papel, do tamanho da caixa. A mesa cinza em
 * volta da folha (folha.css) sai — papel sem margem nem sombra, no canto do quadro, que tem
 * a largura do A4 (editor.css) —, então não há o que medir no documento: só a caixa.
 * @param {HTMLIFrameElement} quadro
 */
function ajustarMiniatura(quadro) {
  const doc = quadro.contentDocument;
  const caixa = quadro.parentElement;
  if (doc?.body) {
    doc.documentElement.style.overflow = "hidden";
    doc.documentElement.style.background = "transparent";
    doc.body.style.margin = "0";
    doc.body.style.boxShadow = "none";
  }
  if (caixa?.clientWidth) quadro.style.transform = `scale(${caixa.clientWidth / A4_LARGURA_PX})`;
}

/**
 * (Re)carrega a miniatura de uma caixa sem mostrar a folha pela metade: a nova carrega
 * escondida, por cima da atual, e só aparece já em escala e sem a mesa — quem olha vê a
 * troca pronta, não o papel com a mesa cinza piscando antes do ajuste.
 * @param {HTMLElement} caixa
 */
function carregarMiniatura(caixa) {
  caixa.querySelectorAll("iframe[data-carregando]").forEach((q) => q.remove());
  const atual = /** @type {HTMLIFrameElement | null} */ (caixa.querySelector("iframe[data-miniatura]"));
  const endereco = atual?.dataset.src || "";
  if (!atual || !endereco) return;
  const nova = /** @type {HTMLIFrameElement} */ (atual.cloneNode(false));
  nova.removeAttribute("src");
  nova.removeAttribute("style");
  nova.setAttribute("data-carregando", "");
  nova.addEventListener("load", () => {
    ajustarMiniatura(nova);
    nova.removeAttribute("data-carregando");
    caixa.querySelectorAll("iframe[data-miniatura]").forEach((q) => { if (q !== nova) q.remove(); });
  }, { once: true });
  // Endereço novo a cada recarga: a folha refeita, não a guardada pelo navegador.
  nova.src = `${endereco}${endereco.includes("?") ? "&" : "?"}miniatura=${Date.now()}`;
  caixa.append(nova);
}

/**
 * Liga um bloco de editores. Devolve o que a página pede a ele de fora (os dados do termo
 * foram gravados: as miniaturas se refazem).
 * @param {HTMLElement} raiz
 */
function iniciar(raiz) {
  const editores = /** @type {HTMLElement[]} */ (Array.from(raiz.querySelectorAll("pc-editor-documento")));
  const botoes = /** @type {HTMLButtonElement[]} */ (Array.from(raiz.querySelectorAll("[data-ir-pagina]")));
  const chaveDe = (/** @type {HTMLElement} */ ed) =>
    /** @type {HTMLElement | null} */ (ed.closest("[data-pagina]"))?.dataset.pagina || "";

  /** @param {HTMLElement} editor */
  const ativar = (editor) => {
    for (const e of editores) e.classList.toggle("editor--ativo", e === editor);
    const chave = chaveDe(editor);
    for (const b of botoes) {
      if (b.dataset.irPagina === chave) b.setAttribute("aria-current", "true");
      else b.removeAttribute("aria-current");
    }
  };
  if (editores[0]) ativar(editores[0]);

  // O cursor entrou numa página (editor-documento.js avisa com `pc-editor:ativo`).
  raiz.addEventListener("pc-editor:ativo", (e) => {
    const editor = /** @type {HTMLElement} */ (e.target).closest("pc-editor-documento");
    if (editor) ativar(/** @type {HTMLElement} */ (editor));
  });

  // Navegador: leva ao título da página e a torna a ativa.
  raiz.addEventListener("click", (e) => {
    const botao = /** @type {HTMLElement} */ (e.target).closest("[data-ir-pagina]");
    if (!botao) return;
    const item = raiz.querySelector(`[data-pagina="${CSS.escape(/** @type {HTMLElement} */ (botao).dataset.irPagina || "")}"]`);
    const editor = /** @type {HTMLElement | null} */ (item?.querySelector("pc-editor-documento") ?? null);
    const titulo = item?.querySelector(".editores__titulo");
    if (editor) ativar(editor);
    titulo?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  });

  // Rolando: a página que ocupa o meio da tela passa a ser a ativa (barra e navegador).
  const observador = new IntersectionObserver((entradas) => {
    for (const entrada of entradas) {
      if (!entrada.isIntersecting) continue;
      const editor = /** @type {HTMLElement} */ (entrada.target).closest("pc-editor-documento");
      if (editor) ativar(/** @type {HTMLElement} */ (editor));
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  for (const e of editores) {
    const folha = e.querySelector(".editor__folha");
    if (folha) observador.observe(folha);
  }

  // "Texto" / "PDF" valem para o bloco todo: no PDF, um arquivo só com todos os documentos
  // (o mesmo de "Gerar"), no lugar das páginas de edição. O clique não chega ao editor (que
  // abriria o PDF só da página dele, com as outras ainda em edição embaixo).
  const pdf = /** @type {HTMLElement | null} */ (raiz.querySelector(".editores__pdf"));
  const quadroPdf = /** @type {HTMLIFrameElement | null} */ (pdf?.querySelector("iframe") ?? null);
  const carregarPdf = () => {
    if (!quadroPdf || !raiz.dataset.pdfTodos) return;
    const url = new URL(raiz.dataset.pdfTodos, window.location.href);
    url.searchParams.set("_", String(Date.now()));
    quadroPdf.src = url.toString();
  };
  /** @param {string} modo */
  const mudarModo = (modo) => {
    const emPdf = modo === "pdf";
    raiz.classList.toggle("editores--pdf", emPdf);
    for (const e of editores) {
      e.classList.toggle("editor--pdf", emPdf);
      e.querySelectorAll("[data-modo]").forEach((b) => b.setAttribute("aria-pressed", String(/** @type {HTMLElement} */ (b).dataset.modo === modo)));
      e.querySelectorAll("[data-so-texto]").forEach((g) => { /** @type {HTMLElement} */ (g).hidden = emPdf; });
    }
    if (pdf) pdf.hidden = !emPdf;
    if (emPdf) carregarPdf();
  };
  raiz.addEventListener("click", (e) => {
    const botao = /** @type {HTMLElement} */ (e.target).closest("[data-modo]");
    if (!(botao instanceof HTMLElement) || !pdf) return;
    e.stopPropagation();
    mudarModo(botao.dataset.modo || "texto");
  }, true);

  // A barra é o cabeçalho do bloco: o índice gruda logo abaixo dela (editor.css).
  const medirBarra = () => {
    const barra = raiz.querySelector(".editor--ativo > .editor__barra");
    if (barra instanceof HTMLElement && barra.offsetHeight) raiz.style.setProperty("--altura-barra", `${barra.offsetHeight}px`);
  };
  new ResizeObserver(medirBarra).observe(raiz);

  // Mostrar/esconder o índice (o botão de painel da barra). Lembra a escolha neste navegador;
  // em tela estreita começa fechado.
  const CHAVE_INDICE = "pc-editores-indice";
  /** @param {boolean} aberto */
  const mostrarIndice = (aberto) => {
    raiz.classList.toggle("editores--sem-indice", !aberto);
    raiz.querySelectorAll("[data-alternar-indice]").forEach((b) => b.setAttribute("aria-expanded", String(aberto)));
    if (aberto) ajustarTodas();
  };
  raiz.addEventListener("click", (e) => {
    if (!/** @type {HTMLElement} */ (e.target).closest("[data-alternar-indice]")) return;
    const aberto = raiz.classList.contains("editores--sem-indice");
    mostrarIndice(aberto);
    try { localStorage.setItem(CHAVE_INDICE, aberto ? "aberto" : "fechado"); } catch { /* sem armazenamento */ }
  });

  // Miniaturas do índice (uma caixa por página; o quadro dentro dela é trocado a cada recarga).
  const caixas = /** @type {HTMLElement[]} */ (Array.from(raiz.querySelectorAll(".editores__miniatura")));
  const ajustarTodas = () => caixas.forEach(
    (c) => c.querySelectorAll("iframe").forEach((q) => ajustarMiniatura(/** @type {HTMLIFrameElement} */ (q))));
  /** @param {string} chave */
  const caixaDe = (chave) => caixas.find(
    (c) => /** @type {HTMLElement | null} */ (c.closest("[data-ir-pagina]"))?.dataset.irPagina === chave);
  caixas.forEach(carregarMiniatura);
  // A caixa muda de largura com a coluna (barra de rolagem do índice, tela): reajusta.
  const observaCaixas = new ResizeObserver(ajustarTodas);
  caixas.forEach((c) => observaCaixas.observe(c));
  raiz.addEventListener("pc-editor:gravado", (e) => {
    const editor = /** @type {HTMLElement} */ (e.target).closest("pc-editor-documento");
    const caixa = editor && caixaDe(chaveDe(/** @type {HTMLElement} */ (editor)));
    if (caixa) carregarMiniatura(caixa);
  });

  /** @type {string | null} */
  let preferencia = null;
  try { preferencia = localStorage.getItem(CHAVE_INDICE); } catch { /* sem armazenamento */ }
  mostrarIndice(preferencia ? preferencia === "aberto" : !matchMedia("(max-width: 767.98px)").matches);
  return {
    // Dados ou texto mudaram: as miniaturas — e o PDF, se é ele que está na tela — se refazem.
    recarregarMiniaturas: () => {
      caixas.forEach(carregarMiniatura);
      if (raiz.classList.contains("editores--pdf")) carregarPdf();
    },
  };
}

/** @param {ParentNode} onde */
const chavesDe = (onde) => Array.from(onde.querySelectorAll("[data-editores] [data-ir-pagina]"),
  (b) => /** @type {HTMLElement} */ (b).dataset.irPagina).join(" ");

const inicial = /** @type {HTMLElement | null} */ (document.querySelector("[data-editores]"));
let bloco = inicial ? iniciar(inicial) : null;

// Texto levado para todas as páginas, ou dados do termo gravados: as miniaturas se refazem
// (as folhas dos editores se refazem sozinhas — editor-documento.js).
document.addEventListener("pc-editor:texto-aplicado", () => bloco?.recarregarMiniaturas());
document.addEventListener("pcpr:dados-salvos", () => bloco?.recarregarMiniaturas());

// A gravação mudou QUAIS documentos o termo emite (um servidor a mais, a viatura): o bloco
// vem da página refeita (autosave.js) com as páginas novas — que já nascem com o texto
// editado dos irmãos (termos._herdar_texto_editado) — e é ligado de novo.
document.addEventListener("pcpr:pagina-refeita", (e) => {
  const pagina = /** @type {Document} */ (/** @type {CustomEvent} */ (e).detail.pagina);
  const atual = document.querySelector("[data-editores]")?.closest("[id]");
  if (!atual || chavesDe(document) === chavesDe(pagina)) return;
  const novo = pagina.getElementById(atual.id);
  if (!novo || atual.contains(document.activeElement)) return;
  atual.replaceWith(document.adoptNode(novo));
  const raiz = /** @type {HTMLElement | null} */ (document.querySelector("[data-editores]"));
  bloco = raiz ? iniciar(raiz) : null;
});

export {};
