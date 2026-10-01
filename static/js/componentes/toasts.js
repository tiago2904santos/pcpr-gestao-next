// @ts-check
/**
 * <pc-toasts> — notificações efêmeras (role="status", não roubam o foco).
 * Fontes: mensagens do Django renderizadas no carregamento e o evento HTMX
 * `HX-Trigger: {"toast": {"nivel": "sucesso", "mensagem": "…"}}`.
 */
const ICONES = /** @type {Record<string, string>} */ ({
  sucesso: "check-circle-2",
  aviso: "alert-triangle",
  perigo: "x-circle",
  info: "info",
});

export class PcToasts extends HTMLElement {
  connectedCallback() {
    this.setAttribute("role", "status");
    this.setAttribute("aria-live", "polite");
    this.sprite = this.dataset.sprite || "";
    this.querySelectorAll(".toast").forEach((t) => this.agendar(/** @type {HTMLElement} */ (t)));
    document.body.addEventListener("toast", (evento) => {
      const d = /** @type {CustomEvent} */ (evento).detail || {};
      this.mostrar(d.mensagem || d.value || "", d.nivel || "info");
    });
  }

  /** @param {string} mensagem @param {string} nivel */
  mostrar(mensagem, nivel = "info") {
    if (!mensagem) return;
    const t = document.createElement("div");
    t.className = `toast toast--${nivel}`;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "icone");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS(svgNS, "use");
    use.setAttribute("href", `${this.sprite}#i-${ICONES[nivel] || "info"}`);
    svg.append(use);
    const texto = document.createElement("div");
    texto.textContent = mensagem;
    const fechar = document.createElement("button");
    fechar.type = "button";
    fechar.className = "toast__fechar";
    fechar.setAttribute("aria-label", "Fechar notificação");
    fechar.textContent = "×";
    t.append(svg, texto, fechar);
    this.append(t);
    this.agendar(t);
  }

  /** @param {HTMLElement} t */
  agendar(t) {
    t.querySelector(".toast__fechar")?.addEventListener("click", () => t.remove());
    // Erros ficam até serem fechados (WCAG 2.2.1); demais somem após 6s.
    if (!t.classList.contains("toast--perigo")) {
      let restante = 6000;
      let inicio = Date.now();
      /** @type {number | undefined} */
      let timer = window.setTimeout(() => t.remove(), restante);
      t.addEventListener("mouseenter", () => {
        window.clearTimeout(timer);
        restante -= Date.now() - inicio;
      });
      t.addEventListener("mouseleave", () => {
        inicio = Date.now();
        timer = window.setTimeout(() => t.remove(), Math.max(restante, 1500));
      });
    }
  }
}

customElements.define("pc-toasts", PcToasts);
