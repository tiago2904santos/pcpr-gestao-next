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
      this.mostrar(d.mensagem || d.value || "", d.nivel || "info", d.link);
    });
    // Sessão expirada num pedido assíncrono (app.js): um aviso só, que fica até ser fechado.
    document.addEventListener("pcpr:sessao-expirada", (evento) => {
      if (this.querySelector("[data-toast-sessao]")) return;
      const d = /** @type {CustomEvent} */ (evento).detail || {};
      this.mostrar(d.mensagem || "Sua sessão terminou — entre de novo.", "perigo",
        { texto: "Entrar de novo", url: d.entrar || "/conta/entrar/" });
      this.lastElementChild?.setAttribute("data-toast-sessao", "");
    });
  }

  /**
   * @param {string} mensagem @param {string} nivel
   * @param {{texto: string, url: string}} [link] uma ação no próprio aviso (ex.: entrar de novo)
   */
  mostrar(mensagem, nivel = "info", link) {
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
    if (link?.url && link.url.startsWith("/") && !link.url.startsWith("//")) {
      const a = document.createElement("a");
      a.className = "toast__acao";
      a.href = link.url;
      a.textContent = link.texto || "Abrir";
      texto.append(" ", a);
    }
    const fechar = document.createElement("button");
    fechar.type = "button";
    fechar.className = "toast__fechar";
    fechar.setAttribute("aria-label", "Fechar notificação");
    fechar.textContent = "×";
    t.append(svg, texto, fechar);
    this.append(t);
    this.agendar(t);
  }

  /**
   * Sai com a animação do Design System (toast-sair) e só então remove do DOM.
   * @param {HTMLElement} t
   */
  remover(t) {
    if (t.classList.contains("toast--saindo")) return;
    t.classList.add("toast--saindo");
    const fim = () => t.remove();
    t.addEventListener("animationend", fim, { once: true });
    window.setTimeout(fim, 400); // reduced-motion ou animação indisponível
  }

  /** @param {HTMLElement} t */
  agendar(t) {
    t.querySelector(".toast__fechar")?.addEventListener("click", () => this.remover(t));
    // Erros ficam até serem fechados (WCAG 2.2.1); demais somem após 6s.
    // A barra de tempo (CSS ::after) acompanha: pausa junto com o cronômetro.
    if (!t.classList.contains("toast--perigo")) {
      let restante = 6000;
      let inicio = Date.now();
      /** @type {number | undefined} */
      let timer = window.setTimeout(() => this.remover(t), restante);
      const pausar = () => {
        window.clearTimeout(timer);
        restante -= Date.now() - inicio;
        t.classList.add("toast--pausado");
      };
      const retomar = () => {
        inicio = Date.now();
        t.classList.remove("toast--pausado");
        timer = window.setTimeout(() => this.remover(t), Math.max(restante, 1500));
      };
      t.addEventListener("mouseenter", pausar);
      t.addEventListener("mouseleave", retomar);
      t.addEventListener("focusin", pausar);
      t.addEventListener("focusout", retomar);
    }
  }
}

customElements.define("pc-toasts", PcToasts);
