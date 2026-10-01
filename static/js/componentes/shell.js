// @ts-check
/**
 * <pc-shell> — comportamento do App Shell.
 *  - ≥1024px: recolhe/expande a navegação lateral (preferência guardada no navegador);
 *  - <1024px: navegação vira gaveta com foco gerenciado, Esc e véu.
 * Sem JavaScript a navegação continua acessível (a lateral é HTML comum).
 */

const CHAVE = "pc:lateral-recolhida";
const LARGURA_GAVETA = 1024;

function lerPreferencia() {
  try {
    return window.localStorage.getItem(CHAVE) === "1";
  } catch {
    return false;
  }
}

/** @param {boolean} valor */
function gravarPreferencia(valor) {
  try {
    window.localStorage.setItem(CHAVE, valor ? "1" : "0");
  } catch {
    /* armazenamento indisponível: preferência só vale nesta página */
  }
}

export class PcShell extends HTMLElement {
  connectedCallback() {
    this.raiz = /** @type {HTMLElement} */ (this.closest(".shell") || document.body);
    this.lateral = /** @type {HTMLElement | null} */ (document.getElementById("navegacao-lateral"));
    this.conteudo = /** @type {HTMLElement | null} */ (document.querySelector(".conteudo"));
    this.botaoGaveta = /** @type {HTMLButtonElement | null} */ (
      document.querySelector("[data-acao='abrir-gaveta']")
    );
    this.botaoRecolher = /** @type {HTMLButtonElement | null} */ (
      document.querySelector("[data-acao='recolher-lateral']")
    );
    this.midia = window.matchMedia(`(max-width: ${LARGURA_GAVETA - 0.02}px)`);

    if (lerPreferencia()) this.raiz.classList.add("shell--recolhido");
    this.atualizarRecolher();

    this.botaoGaveta?.addEventListener("click", () => this.alternarGaveta());
    this.botaoRecolher?.addEventListener("click", () => this.alternarRecolhida());
    this.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.gavetaAberta()) {
        this.fecharGaveta();
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.gavetaAberta()) this.fecharGaveta();
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
    if (!this.raiz || !this.lateral) return;
    this.raiz.classList.add("shell--gaveta-aberta");
    this.botaoGaveta?.setAttribute("aria-expanded", "true");
    this.conteudo?.setAttribute("inert", "");
    const veu = document.createElement("div");
    veu.className = "shell__veu";
    veu.dataset.veu = "";
    veu.addEventListener("click", () => this.fecharGaveta());
    this.raiz.append(veu);
    const primeiro = /** @type {HTMLElement | null} */ (
      this.lateral.querySelector("[aria-current='page'], a, button")
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

  alternarRecolhida() {
    if (!this.raiz) return;
    const recolhida = this.raiz.classList.toggle("shell--recolhido");
    gravarPreferencia(recolhida);
    this.atualizarRecolher();
  }

  atualizarRecolher() {
    const recolhida = this.raiz?.classList.contains("shell--recolhido") ?? false;
    if (!this.botaoRecolher) return;
    this.botaoRecolher.setAttribute("aria-pressed", String(recolhida));
    const rotulo = recolhida ? "Expandir menu" : "Recolher menu";
    this.botaoRecolher.setAttribute("aria-label", rotulo);
    this.botaoRecolher.dataset.dica = recolhida ? rotulo : "";
  }
}

customElements.define("pc-shell", PcShell);
