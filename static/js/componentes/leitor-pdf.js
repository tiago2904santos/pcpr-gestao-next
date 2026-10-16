// @ts-check
/** Prévia local, uma página por vez: funciona sem plug-in nativo do navegador. */
const caixa = document.querySelector("[data-leitor-pdf]");
if (caixa instanceof HTMLElement) iniciar(caixa);

/** @param {HTMLElement} raiz */
async function iniciar(raiz) {
  const canvas = /** @type {HTMLCanvasElement} */ (raiz.querySelector("canvas"));
  const status = /** @type {HTMLElement} */ (raiz.querySelector("[data-pdf-status]"));
  const texto = /** @type {HTMLElement} */ (raiz.querySelector("[data-pdf-texto]"));
  const visor = /** @type {HTMLElement} */ (raiz.querySelector("[data-pdf-visor]"));
  const anterior = /** @type {HTMLButtonElement} */ (raiz.querySelector("[data-pdf-anterior]"));
  const proxima = /** @type {HTMLButtonElement} */ (raiz.querySelector("[data-pdf-proxima]"));
  let pagina = 1, zoom = 1, versao = 0;
  /** @type {any} */
  let renderizacao = null;
  try {
    const fonte = raiz.dataset.pdfModulo || "";
    const pdfjs = await import(fonte);
    pdfjs.GlobalWorkerOptions.workerSrc = raiz.dataset.pdfWorker;
    const recursos = new URL(".", new URL(fonte, location.href)).href;
    const documento = await pdfjs.getDocument({url: raiz.dataset.pdfUrl,
      cMapUrl: recursos + "cmaps/", cMapPacked: true,
      standardFontDataUrl: recursos + "standard_fonts/",
      wasmUrl: recursos + "wasm/",
      isEvalSupported: false, useWasm: false, disableFontFace: true}).promise;
    async function desenhar() {
      const atual = ++versao;
      renderizacao?.cancel();
      status.textContent = `Página ${pagina} de ${documento.numPages} · ${Math.round(zoom * 100)}%`;
      anterior.disabled = pagina <= 1; proxima.disabled = pagina >= documento.numPages;
      try {
        const folha = await documento.getPage(pagina);
        if (atual !== versao) return;
        const base = folha.getViewport({scale: 1});
        const escala = Math.max(200, visor.clientWidth - 24) / base.width * zoom;
        const janela = folha.getViewport({scale: escala});
        const densidade = Math.min(2, window.devicePixelRatio || 1);
        // Limite de pixels mantém zoom legível sem reservar canvases gigantes.
        const fator = Math.min(densidade, Math.sqrt(16_000_000 / (janela.width * janela.height)));
        canvas.width = Math.ceil(janela.width * fator); canvas.height = Math.ceil(janela.height * fator);
        canvas.style.width = `${janela.width}px`; canvas.style.height = `${janela.height}px`;
        canvas.setAttribute("aria-label", `Página ${pagina} do documento`);
        renderizacao = folha.render({canvas, canvasContext: canvas.getContext("2d"),
          viewport: janela, transform: [fator, 0, 0, fator, 0, 0]});
        await renderizacao.promise;
        if (atual !== versao) return;
        raiz.dataset.pdfPronto = "true";
        raiz.dataset.pdfZoom = String(Math.round(zoom * 100));
        const conteudo = await folha.getTextContent();
        texto.textContent = conteudo.items.map((/** @type {{str?: string}} */ i) => i.str || "").join(" ");
      } catch (erro) {
        if (erro instanceof Error && erro.name === "RenderingCancelledException") return;
        console.warn("Não foi possível renderizar o PDF.", erro);
        status.textContent = "Não foi possível mostrar esta página. Use Abrir ampliado para abrir o PDF.";
      }
    }
    anterior.addEventListener("click", () => { if (pagina > 1) { pagina--; desenhar(); } });
    proxima.addEventListener("click", () => { if (pagina < documento.numPages) { pagina++; desenhar(); } });
    raiz.querySelectorAll("[data-pdf-zoom]").forEach((botao) => {
      botao.addEventListener("click", () => { zoom = Number(botao.getAttribute("data-pdf-zoom")); desenhar(); });
    });
    await desenhar();
  } catch (erro) {
    console.warn("Não foi possível carregar o leitor PDF.", erro);
    status.textContent = "A prévia não carregou. Use Abrir ampliado para abrir o PDF.";
  }
}
