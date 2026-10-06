// @ts-check
/**
 * <pc-escolhas> — várias escolhas num campo do tamanho de um select (ex.: os programas do
 * plano). O botão `[data-gatilho]` mostra o que está marcado ("A, B" ou "A, B e mais 2") e
 * abre o painel `[data-painel]` com as caixas; as caixas continuam sendo o valor do
 * formulário. Sem JavaScript o botão some (CSS `scripting: none`) e as caixas ficam à vista.
 *
 * Teclado: ↓/Enter/Espaço no botão abrem e focam a 1ª caixa; ↓/↑ andam entre as caixas;
 * Esc fecha e volta ao botão; sair do campo (Tab, clique fora) fecha.
 */

export class PcEscolhas extends HTMLElement {
  connectedCallback() {
    const gatilho = /** @type {HTMLButtonElement | null} */ (this.querySelector("[data-gatilho]"));
    const painel = /** @type {HTMLElement | null} */ (this.querySelector("[data-painel]"));
    if (!gatilho || !painel || this.dataset.pronto) return;
    this.dataset.pronto = "1";
    this.gatilho = gatilho;
    this.painel = painel;
    painel.hidden = true;

    gatilho.addEventListener("click", () => (painel.hidden ? this.abrir() : this.fechar()));
    gatilho.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && painel.hidden) {
        e.preventDefault();
        this.abrir();
      }
    });
    painel.addEventListener("keydown", (e) => {
      const caixas = this.caixas();
      const atual = caixas.indexOf(/** @type {HTMLInputElement} */ (document.activeElement));
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const passo = e.key === "ArrowDown" ? 1 : -1;
        caixas[(atual + passo + caixas.length) % caixas.length]?.focus();
      }
    });
    this.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !painel.hidden) {
        e.stopPropagation();
        this.fechar();
        gatilho.focus();
      }
    });
    // Clicar numa linha da lista não tira o foco dela (senão a lista fecharia antes de marcar).
    painel.addEventListener("mousedown", (e) => {
      if (/** @type {HTMLElement} */ (e.target).closest("label")) e.preventDefault();
    });
    // Tab para fora fecha; o clique fora é com o `pointerdown` abaixo.
    this.addEventListener("focusout", (e) => {
      const destino = /** @type {Node | null} */ (e.relatedTarget);
      if (destino && !this.contains(destino)) this.fechar();
    });
    document.addEventListener("pointerdown", (e) => {
      if (!painel.hidden && !this.contains(/** @type {Node} */ (e.target))) this.fechar();
    });
    this.addEventListener("change", () => this.resumir());
    // "Outro": o texto digitado ao lado entra no resumo.
    this.closest(".campos")?.addEventListener("input", () => this.resumir());
    this.resumir();
  }

  /** @returns {HTMLInputElement[]} */
  caixas() {
    return Array.from(this.querySelectorAll("[data-painel] input[type='checkbox']"));
  }

  abrir() {
    if (!this.painel || !this.gatilho) return;
    this.painel.hidden = false;
    this.gatilho.setAttribute("aria-expanded", "true");
    (this.caixas().find((c) => c.checked) ?? this.caixas()[0])?.focus();
  }

  fechar() {
    if (!this.painel || !this.gatilho || this.painel.hidden) return;
    this.painel.hidden = true;
    this.gatilho.setAttribute("aria-expanded", "false");
  }

  /** O botão diz o que está marcado. */
  resumir() {
    const resumo = this.querySelector("[data-resumo]");
    if (!resumo || !this.gatilho) return;
    const nomes = this.caixas().filter((c) => c.checked).map((c) => {
      if (c.name.endsWith("_outro")) {
        const texto = /** @type {HTMLInputElement | null} */ (
          this.closest(".campos")?.querySelector(`input[name='${c.name}s']`) ?? null);
        return texto?.value.trim() || "Outro";
      }
      return c.closest("label")?.textContent?.trim() || "";
    }).filter(Boolean);
    const texto = nomes.length > 2
      ? `${nomes.slice(0, 2).join(", ")} e mais ${nomes.length - 2}`
      : nomes.join(", ");
    resumo.textContent = texto || this.dataset.vazio || "Selecione";
    this.gatilho.classList.toggle("seletor__gatilho--vazio", !texto);
    this.gatilho.title = nomes.join(", ");
  }
}

customElements.define("pc-escolhas", PcEscolhas);
