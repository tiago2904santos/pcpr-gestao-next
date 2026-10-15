// @ts-check
/**
 * Visualizador dos documentos da viagem (viagem/_visualizador.html). Os cartões da trilha
 * (`a[data-visualizar]`) abrem o modal em vez de navegar — Ctrl/⌘/clique do meio continuam
 * abrindo a folha de edição, e sem JavaScript o link leva até ela.
 *
 * - Documento pronto (`data-paginas`, as folhas em JSON, cada uma com o PDF e o "anexar"):
 *   a folha flutua sobre a página escurecida, sem a mesa cinza; mais de uma (ofício e
 *   justificativa, os termos de cada servidor): a escolha no topo.
 * - Não pronto, com pendência ou roteiro: o resumo flutua (o fragmento das listas, por HTMX,
 *   com as ações no rodapé).
 * - Anexo da solicitação: o arquivo como é.
 * - Setas (e ← →) passam entre os documentos do mesmo passo; Esc fecha e devolve o foco.
 * - Ações rápidas: imprimir, baixar, baixar todos (o ZIP da viagem), anexar a via assinada
 *   (a janela de assinado.js) e editar.
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
  const posicao = $("[data-v-posicao]");
  const anterior = /** @type {HTMLButtonElement} */ ($("[data-v-anterior]"));
  const proximo = /** @type {HTMLButtonElement} */ ($("[data-v-proximo]"));
  const caixaPagina = $("[data-v-pagina]");
  const paginas = /** @type {HTMLSelectElement} */ ($("[data-v-paginas]"));
  const documento = $("[data-v-documento]");
  const folha = /** @type {HTMLIFrameElement} */ ($("[data-v-folha]"));
  const cartao = $("[data-v-cartao]");
  const resumo = $("[data-v-resumo]");
  const carregando = resumo.innerHTML;
  const imprimir = $("[data-v-imprimir]");
  const baixar = /** @type {HTMLAnchorElement} */ ($("[data-v-baixar]"));
  const todos = $("[data-v-todos]");
  const anexar = $("[data-v-anexar]");
  const editar = /** @type {HTMLAnchorElement} */ ($("[data-v-editar]"));

  /** @type {HTMLAnchorElement[]} */
  let grupo = [];
  let indice = 0;
  /** @type {{rotulo: string, url: string, pdf?: string, anexar?: string}[]} */
  let lista = [];
  let anexo = false;

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
    baixar.hidden = !pagina.pdf;
    if (pagina.pdf) baixar.href = pagina.pdf;
    anexar.hidden = !pagina.anexar;
    if (pagina.anexar) {
      anexar.dataset.anexarAssinado = pagina.anexar;
      anexar.dataset.assinadoTitulo = `${titulo.textContent} · ${pagina.rotulo}`;
      anexar.dataset.assinadoVoltar = `${location.pathname}#documentos`;
    }
  };

  /** @param {HTMLAnchorElement} item */
  const mostrar = (item) => {
    const dados = item.dataset;
    tipo.textContent = dados.tipo || "";
    titulo.textContent = dados.titulo || "Documento";
    posicao.textContent = grupo.length > 1 ? `${indice + 1} de ${grupo.length}` : "";
    anterior.hidden = proximo.hidden = grupo.length < 2;
    anterior.disabled = indice === 0;
    proximo.disabled = indice === grupo.length - 1;
    editar.hidden = !dados.abrir;
    if (dados.abrir) editar.href = dados.abrir;
    todos.hidden = !document.getElementById("baixar-tudo");

    try { lista = dados.paginas ? JSON.parse(dados.paginas) : []; } catch { lista = []; }
    anexo = !dados.resumo;
    const temDocumento = lista.length > 0;
    documento.hidden = !temDocumento;
    cartao.hidden = temDocumento;
    imprimir.hidden = !temDocumento;
    d.classList.toggle("visualizador--anexo", anexo);
    caixaPagina.hidden = lista.length < 2;
    paginas.replaceChildren(...lista.map((p, i) => new Option(p.rotulo, String(i))));
    if (temDocumento) {
      folha.title = `${dados.titulo}: documento`;
      mostrarPagina(0);
    } else {
      folha.removeAttribute("src");
      baixar.hidden = anexar.hidden = true;
      resumo.innerHTML = carregando;
      const htmx = /** @type {any} */ (window).htmx;
      if (htmx && dados.resumo) htmx.ajax("GET", dados.resumo, { target: resumo, swap: "innerHTML" });
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
  paginas.addEventListener("change", () => mostrarPagina(Number(paginas.value)));
  imprimir.addEventListener("click", () => {
    try {
      folha.contentWindow?.focus();
      folha.contentWindow?.print();
    } catch {
      window.open(folha.src, "_blank", "noopener");
    }
  });
  d.addEventListener("keydown", (e) => {
    const alvo = /** @type {Element} */ (e.target);
    if (alvo.closest("input, textarea, select, [contenteditable]")) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); ir(indice - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); ir(indice + 1); }
  });
  // Clique no véu (fora do documento e da barra) fecha, como o Esc.
  d.addEventListener("click", (e) => {
    if (e.target === d || /** @type {Element} */ (e.target).matches(".visualizador__palco")) d.close();
  });
  d.addEventListener("close", () => {
    folha.removeAttribute("src");
    grupo[indice]?.focus();
  });

  document.addEventListener("click", (e) => {
    const item = /** @type {HTMLAnchorElement | null} */ (
      /** @type {Element} */ (e.target).closest("a[data-visualizar]"));
    if (!item || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    grupo = /** @type {HTMLAnchorElement[]} */ (Array.from(document.querySelectorAll(
      `a[data-visualizar][data-grupo="${item.dataset.grupo}"]`)));
    indice = Math.max(0, grupo.indexOf(item));
    mostrar(item);
    if (!d.open) d.showModal();
  });
}

document.querySelectorAll("[data-visualizador]").forEach((d) => ligar(/** @type {HTMLElement} */ (d)));

export {};
