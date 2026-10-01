// @ts-check
/**
 * <pc-shell> — comportamento do App Shell.
 *  - ≥768px (tablet e desktop): o menu superior é uma barra horizontal comum;
 *  - <768px (celular): o ☰ abre o menu numa gaveta lateral temporária, com foco
 *    gerenciado, Esc, véu e conteúdo `inert` enquanto aberta.
 * Sem JavaScript a navegação continua acessível (HTML comum).
 */

const LARGURA_GAVETA = 768;

export class PcShell extends HTMLElement {
  connectedCallback() {
    this.raiz = /** @type {HTMLElement} */ (this.closest(".shell") || document.body);
    this.navegacao = /** @type {HTMLElement | null} */ (
      document.getElementById("navegacao-principal")
    );
    this.conteudo = /** @type {HTMLElement | null} */ (document.querySelector(".shell__corpo"));
    this.botaoGaveta = /** @type {HTMLButtonElement | null} */ (
      document.querySelector("[data-acao='abrir-gaveta']")
    );
    this.midia = window.matchMedia(`(max-width: ${LARGURA_GAVETA - 0.02}px)`);
    this.botaoGaveta?.addEventListener("click", () => this.alternarGaveta());
    document.addEventListener("keydown", (e) => {
      // Esc com um menu suspenso aberto fecha só o menu (<pc-menu> chama preventDefault).
      if (e.key === "Escape" && !e.defaultPrevented && this.gavetaAberta()) this.fecharGaveta();
    });
    this.midia.addEventListener("change", () => this.fecharGaveta(false));
  }

  gavetaAberta() {
    return this.raiz?.classList.contains("shell--gaveta-aberta") ?? false;
  }

  alternarGaveta() {
    if (this.gavetaAberta()) this.fecharGaveta();
    else this.abrirGaveta();
  }

  abrirGaveta() {
    if (!this.raiz || !this.navegacao) return;
    this.raiz.classList.add("shell--gaveta-aberta");
    this.botaoGaveta?.setAttribute("aria-expanded", "true");
    this.conteudo?.setAttribute("inert", "");
    const veu = document.createElement("div");
    veu.className = "shell__veu";
    veu.dataset.veu = "";
    veu.addEventListener("click", () => this.fecharGaveta());
    this.raiz.append(veu);
    const primeiro = /** @type {HTMLElement | null} */ (
      this.navegacao.querySelector("[aria-current='page'], a, button")
    );
    primeiro?.focus();
  }

  fecharGaveta(devolverFoco = true) {
    if (!this.raiz) return;
    const estavaAberta = this.gavetaAberta();
    this.raiz.classList.remove("shell--gaveta-aberta");
    this.botaoGaveta?.setAttribute("aria-expanded", "false");
    this.conteudo?.removeAttribute("inert");
    this.raiz.querySelectorAll("[data-veu]").forEach((v) => v.remove());
    if (estavaAberta && devolverFoco) this.botaoGaveta?.focus();
  }
}

customElements.define("pc-shell", PcShell);
