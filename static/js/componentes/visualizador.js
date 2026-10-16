// @ts-check
/**
 * Visualizador dos documentos da viagem (viagem/_visualizador.html). Os cartões da trilha
 * (`a[data-visualizar]`) abrem o modal em vez de navegar — Ctrl/⌘/clique do meio continuam
 * abrindo a folha de edição, e sem JavaScript o link leva até ela.
 *
 * - Documento pronto (`data-paginas`, as folhas em JSON, cada uma com o PDF e o "anexar"):
 *   a folha flutua sobre a página escurecida (#dialogo-documento); mais de uma (ofício e
 *   justificativa, os termos de cada servidor): a escolha no topo.
 * - Não pronto, com pendência ou roteiro: a janela de resumo de sempre (#dialogo-resumo, a
 *   das listas), com as setas numa barra embaixo.
 * - Anexo da solicitação: o arquivo como é.
 * - Setas (e ← →) passam por todos os documentos da viagem, na ordem da trilha, trocando de
 *   janela quando o próximo é de outro jeito; Esc fecha e devolve o foco ao cartão.
 * - Baixar: a janela "Baixar documentos" (baixar.js) com as peças do documento (`data-baixar`);
 *   sem ela (o anexo, ou quem não pode gerar), o PDF direto.
 */

const A4_LARGURA_PX = (210 / 25.4) * 96;  // a folha tem a largura do A4, com a mesa em volta
const MARGEM_DA_MESA_PX = 48;

/**
 * @param {HTMLDialogElement} visor
 * @param {HTMLDialogElement} janela
 */
function ligar(visor, janela) {
  if (visor.dataset.pronto) return;
  visor.dataset.pronto = "1";
  const $ = (/** @type {string} */ s) => /** @type {HTMLElement} */ (
    visor.querySelector(s) || janela.querySelector(s));
  const titulo = $("[data-v-titulo]");
  const tipo = $("[data-v-tipo]");
  const posicao = $("[data-v-posicao]");
  const caixaPagina = $("[data-v-pagina]");
  const paginas = /** @type {HTMLSelectElement} */ ($("[data-v-paginas]"));
  const documento = $("[data-v-documento]");
  const folha = /** @type {HTMLIFrameElement} */ ($("[data-v-folha]"));
  const imprimir = $("[data-v-imprimir]");
  const baixar = $("[data-v-baixar]");
  const baixarArquivo = /** @type {HTMLAnchorElement} */ ($("[data-v-baixar-arquivo]"));
  const anexar = $("[data-v-anexar]");
  const editar = /** @type {HTMLAnchorElement} */ ($("[data-v-editar]"));
  const resumo = /** @type {HTMLElement} */ (janela.querySelector("[data-corpo-dialogo]"));
  const carregando = resumo.innerHTML;
  const barra = $("[data-r-barra]");
  const rPosicao = $("[data-r-posicao]");
  /** @type {HTMLButtonElement[]} */
  const anteriores = [$("[data-v-anterior]"), $("[data-r-anterior]")].map((b) => /** @type {HTMLButtonElement} */ (b));
  /** @type {HTMLButtonElement[]} */
  const proximos = [$("[data-v-proximo]"), $("[data-r-proximo]")].map((b) => /** @type {HTMLButtonElement} */ (b));
  const temJanelaBaixar = Boolean(document.getElementById("dialogo-baixar"));

  /** @type {HTMLAnchorElement[]} */
  let itens = [];
  let indice = 0;
  /** @type {{rotulo: string, url: string, pdf?: string, anexar?: string}[]} */
  let lista = [];
  let anexo = false;
  // Janelas fechadas na troca (o "close" chega depois): essas não devolvem o foco ao cartão.
  /** @type {Set<HTMLDialogElement>} */
  const trocadas = new Set();

  // A folha flutua: sem a mesa cinza (o fundo é o véu do modal) e na largura que cabe.
  const ajustar = () => {
    if (anexo) return;
    const doc = folha.contentDocument;
    if (!doc?.documentElement || !documento.clientWidth) return;
    doc.documentElement.style.background = "transparent";
    const fator = Math.min(1, (documento.clientWidth - 2) / (A4_LARGURA_PX + MARGEM_DA_MESA_PX));
    doc.documentElement.style.setProperty("zoom", String(fator));
  };
  folha.addEventListener("load", ajustar);
  new ResizeObserver(ajustar).observe(documento);

  /** @param {number} i */
  const mostrarPagina = (i) => {
    const pagina = lista[i];
    if (!pagina) return;
    folha.src = pagina.url;
    const item = itens[indice];
    const modal = Boolean(item?.dataset.baixar) && temJanelaBaixar;
    baixar.hidden = !modal;
    baixarArquivo.hidden = modal || !pagina.pdf;
    if (!modal && pagina.pdf) baixarArquivo.href = pagina.pdf;
    anexar.hidden = !pagina.anexar;
    if (pagina.anexar) {
      anexar.dataset.anexarAssinado = pagina.anexar;
      anexar.dataset.assinadoTitulo = `${titulo.textContent} · ${pagina.rotulo}`;
      anexar.dataset.assinadoVoltar = `${location.pathname}#documentos`;
    }
  };

  /** @param {HTMLDialogElement} abrir @param {HTMLDialogElement} fechar */
  const trocar = (abrir, fechar) => {
    if (fechar.open) {
      trocadas.add(fechar);
      fechar.close();
    }
    if (!abrir.open) abrir.showModal();
  };

  const setas = () => {
    const texto = itens.length > 1 ? `${indice + 1} de ${itens.length}` : "";
    posicao.textContent = rPosicao.textContent = texto;
    barra.hidden = itens.length < 2;
    for (const b of anteriores) { b.hidden = itens.length < 2; b.disabled = indice === 0; }
    for (const b of proximos) { b.hidden = itens.length < 2; b.disabled = indice === itens.length - 1; }
  };

  /** @param {HTMLAnchorElement} item */
  const mostrar = (item) => {
    const dados = item.dataset;
    try { lista = dados.paginas ? JSON.parse(dados.paginas) : []; } catch { lista = []; }
    setas();
    if (!lista.length) {
      // O resumo de sempre, na janela das listas.
      folha.removeAttribute("src");
      resumo.innerHTML = carregando;
      trocar(janela, visor);
      const htmx = /** @type {any} */ (window).htmx;
      if (htmx && dados.resumo) htmx.ajax("GET", dados.resumo, { target: resumo, swap: "innerHTML" });
      return;
    }
    tipo.textContent = dados.tipo || "";
    titulo.textContent = dados.titulo || "Documento";
    editar.hidden = !dados.abrir;
    if (dados.abrir) editar.href = dados.abrir;
    if (dados.baixar) {
      baixar.dataset.baixarDocumentos = dados.baixar;
      baixar.dataset.baixarTitulo = dados.titulo || "";
    } else {
      delete baixar.dataset.baixarDocumentos;
    }
    anexo = !dados.resumo;
    imprimir.hidden = false;
    visor.classList.toggle("visualizador--anexo", anexo);
    caixaPagina.hidden = lista.length < 2;
    paginas.replaceChildren(...lista.map((p, i) => new Option(p.rotulo, String(i))));
    folha.title = `${dados.titulo}: documento`;
    mostrarPagina(0);
    trocar(visor, janela);
  };

  /** @param {number} novo */
  const ir = (novo) => {
    if (novo < 0 || novo >= itens.length || novo === indice) return;
    indice = novo;
    mostrar(itens[indice]);
  };

  for (const b of anteriores) b.addEventListener("click", () => ir(indice - 1));
  for (const b of proximos) b.addEventListener("click", () => ir(indice + 1));
  paginas.addEventListener("change", () => mostrarPagina(Number(paginas.value)));
  imprimir.addEventListener("click", () => {
    try {
      folha.contentWindow?.focus();
      folha.contentWindow?.print();
    } catch {
      window.open(folha.src, "_blank", "noopener");
    }
  });
  for (const d of [visor, janela]) {
    d.addEventListener("keydown", (e) => {
      const alvo = /** @type {Element} */ (e.target);
      if (alvo.closest("input, textarea, select, [contenteditable]")) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); ir(indice - 1); }
      if (e.key === "ArrowRight") { e.preventDefault(); ir(indice + 1); }
    });
    d.addEventListener("close", () => {
      if (d === visor) folha.removeAttribute("src");
      if (!trocadas.delete(d)) itens[indice]?.focus();
    });
  }
  // Clique no véu (fora do documento e da barra) fecha, como o Esc.
  visor.addEventListener("click", (e) => {
    if (e.target === visor || /** @type {Element} */ (e.target).matches(".visualizador__palco")) visor.close();
  });

  document.addEventListener("click", (e) => {
    const item = /** @type {HTMLAnchorElement | null} */ (
      /** @type {Element} */ (e.target).closest("a[data-visualizar]"));
    if (!item || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    itens = /** @type {HTMLAnchorElement[]} */ (Array.from(document.querySelectorAll("a[data-visualizar]")));
    indice = Math.max(0, itens.indexOf(item));
    mostrar(item);
  });
}

const visor = document.querySelector("dialog[data-visualizador]");
const janela = document.querySelector("dialog[data-visualizador-resumo]");
if (visor instanceof HTMLDialogElement && janela instanceof HTMLDialogElement) ligar(visor, janela);

export {};
