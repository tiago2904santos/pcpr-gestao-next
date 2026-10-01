// @ts-check
/**
 * <pc-abas> — abas no cliente (WAI-ARIA tabs, ativação automática).
 *   <pc-abas><div role="tablist" class="abas">
 *     <button role="tab" class="aba" aria-controls="p1" aria-selected="true">…</button>…
 *   </div><div role="tabpanel" id="p1">…</div>…</pc-abas>
 * Abas que trocam de página (filtros de lista) são links comuns, não este componente.
 */
export class PcAbas extends HTMLElement {
  connectedCallback() {
    this.abas = /** @type {HTMLElement[]} */ (Array.from(this.querySelectorAll("[role='tab']")));
    this.abas.forEach((aba, i) => {
      aba.addEventListener("click", () => this.selecionar(i));
      aba.addEventListener("keydown", (e) => {
        const n = this.abas?.length || 0;
        if (e.key === "ArrowRight") this.selecionar((i + 1) % n, true);
        else if (e.key === "ArrowLeft") this.selecionar((i - 1 + n) % n, true);
        else if (e.key === "Home") this.selecionar(0, true);
        else if (e.key === "End") this.selecionar(n - 1, true);
      });
    });
    const inicial = Math.max(0, this.abas.findIndex((a) => a.getAttribute("aria-selected") === "true"));
    this.selecionar(inicial);
  }

  /** @param {number} indice @param {boolean} [focar] */
  selecionar(indice, focar = false) {
    this.abas?.forEach((aba, i) => {
      const ativa = i === indice;
      aba.setAttribute("aria-selected", String(ativa));
      aba.tabIndex = ativa ? 0 : -1;
      const painel = document.getElementById(aba.getAttribute("aria-controls") || "");
      if (painel) painel.hidden = !ativa;
      if (ativa && focar) aba.focus();
    });
  }
}

customElements.define("pc-abas", PcAbas);
