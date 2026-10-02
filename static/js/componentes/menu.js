// @ts-check
/**
 * <pc-menu> — menu suspenso acessível (padrão "menu button" da WAI-ARIA).
 *
 *   <pc-menu class="menu">
 *     <button type="button" data-menu-botao aria-haspopup="menu">Ações</button>
 *     <div class="menu__painel" role="menu" hidden>
 *       <a role="menuitem" class="menu__item" href="…">Abrir</a>
 *     </div>
 *   </pc-menu>
 *
 * Teclado: Enter/Espaço/↓ abrem; ↑/↓/Home/End navegam; Esc fecha e devolve o foco.
 */
export class PcMenu extends HTMLElement {
  connectedCallback() {
    this.botao = /** @type {HTMLButtonElement} */ (this.querySelector("[data-menu-botao]"));
    this.painel = /** @type {HTMLElement} */ (this.querySelector("[role='menu']"));
    if (!this.botao || !this.painel) return;
    if (!this.painel.id) this.painel.id = `menu-${Math.random().toString(36).slice(2, 9)}`;
    this.botao.setAttribute("aria-controls", this.painel.id);
    this.botao.setAttribute("aria-expanded", "false");

    this.botao.addEventListener("click", () => (this.aberto() ? this.fechar() : this.abrir()));
    this.botao.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.abrir();
      }
    });
    this.painel.addEventListener("keydown", (e) => this.teclado(e));
    this.fora = (/** @type {Event} */ e) => {
      if (!this.contains(/** @type {Node} */ (e.target))) this.fechar(false);
    };
  }

  disconnectedCallback() {
    if (this.fora) document.removeEventListener("pointerdown", this.fora);
  }

  aberto() {
    return this.botao?.getAttribute("aria-expanded") === "true";
  }

  itens() {
    return /** @type {HTMLElement[]} */ (
      Array.from(this.painel?.querySelectorAll("[role='menuitem']:not([aria-disabled='true'])") ?? [])
    );
  }

  abrir() {
    if (!this.botao || !this.painel) return;
    this.painel.hidden = false;
    this.botao.setAttribute("aria-expanded", "true");
    if (this.fora) document.addEventListener("pointerdown", this.fora);
    this.encaixar();
    this.itens()[0]?.focus();
  }

  /** O painel nunca sai da tela: abre para o lado em que cabe (celular, botão à esquerda). */
  encaixar() {
    if (!this.painel) return;
    this.painel.classList.remove("menu__painel--forcar-esquerda", "menu__painel--forcar-direita");
    const r = this.painel.getBoundingClientRect();
    if (r.left < 0) this.painel.classList.add("menu__painel--forcar-esquerda");
    else if (r.right > window.innerWidth) this.painel.classList.add("menu__painel--forcar-direita");
  }

  fechar(devolverFoco = true) {
    if (!this.botao || !this.painel || !this.aberto()) return;
    this.painel.hidden = true;
    this.botao.setAttribute("aria-expanded", "false");
    if (this.fora) document.removeEventListener("pointerdown", this.fora);
    if (devolverFoco) this.botao.focus();
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    const itens = this.itens();
    const i = itens.indexOf(/** @type {HTMLElement} */ (document.activeElement));
    const ir = (/** @type {number} */ n) => itens[(n + itens.length) % itens.length]?.focus();
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); ir(i + 1); break;
      case "ArrowUp": e.preventDefault(); ir(i - 1); break;
      case "Home": e.preventDefault(); ir(0); break;
      case "End": e.preventDefault(); ir(itens.length - 1); break;
      case "Escape": e.preventDefault(); this.fechar(); break;
      case "Tab": this.fechar(false); break;
      default: break;
    }
  }
}

customElements.define("pc-menu", PcMenu);
