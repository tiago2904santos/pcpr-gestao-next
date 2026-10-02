// @ts-check
/**
 * <pc-select> — lista de escolha própria sobre um <select> comum (padrão "Select-Only
 * Combobox" do WAI-ARIA APG). O <select> continua sendo o valor do formulário e o que
 * funciona sem JavaScript; aqui ele fica oculto e um botão com role="combobox" o substitui.
 *
 * Fechado: ↓/↑/Enter/Espaço abrem; letras saltam para a opção. Aberto: ↓/↑/Home/End
 * movem, Enter/Espaço/Tab escolhem, Esc fecha sem mudar.
 */

import { abrirEspaco } from "./seletor-base.js";
import { icone } from "./icone.js";

let contador = 0;
/** @param {string} t */
const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export class PcSelect extends HTMLElement {
  ativo = 0;
  busca = "";
  /** @type {number | undefined} */
  atrasoBusca = undefined;

  connectedCallback() {
    const select = /** @type {HTMLSelectElement | null} */ (this.querySelector("select"));
    if (!select || this.dataset.pronto) return;
    this.dataset.pronto = "1";
    contador += 1;
    this.select = select;

    const gatilho = document.createElement("button");
    gatilho.type = "button";
    gatilho.className = `${select.className || "selecao"} seletor__gatilho`;
    gatilho.id = select.id ? `${select.id}-gatilho` : `pcsel-${contador}`;
    gatilho.setAttribute("role", "combobox");
    gatilho.setAttribute("aria-haspopup", "listbox");
    gatilho.setAttribute("aria-expanded", "false");
    for (const atributo of ["aria-describedby", "aria-invalid", "aria-label"]) {
      const valor = select.getAttribute(atributo);
      if (valor) gatilho.setAttribute(atributo, valor);
    }
    gatilho.disabled = select.disabled;
    const rotulo = select.id ? document.querySelector(`label[for="${select.id}"]`) : null;
    if (rotulo) rotulo.setAttribute("for", gatilho.id);
    this.valor = document.createElement("span");
    this.valor.className = "seletor__valor";
    // Seta de verdade, dentro do botão: desenhá-la no fundo (como no <select> sem JS)
    // a fazia sumir no hover e no foco, que reescrevem o atalho `background`.
    gatilho.append(this.valor, icone("chevron-down", "icone seletor__seta"));

    const lista = document.createElement("ul");
    lista.className = "combobox__lista seletor__lista";
    lista.id = `${gatilho.id}-lista`;
    lista.setAttribute("role", "listbox");
    lista.tabIndex = -1;
    if (rotulo) {
      rotulo.id ||= `${gatilho.id}-rotulo`;
      lista.setAttribute("aria-labelledby", rotulo.id);
    }
    lista.hidden = true;
    gatilho.setAttribute("aria-controls", lista.id);

    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.after(gatilho, lista);
    this.gatilho = gatilho;
    this.lista = lista;
    this.classList.add("seletor--ativo");
    this.atualizarGatilho();

    gatilho.addEventListener("click", () => (this.aberta ? this.fechar() : this.abrir()));
    gatilho.addEventListener("keydown", (e) => this.teclado(e));
    gatilho.addEventListener("blur", () => window.setTimeout(() => {
      if (document.activeElement !== gatilho) this.fechar();
    }, 120));
    lista.addEventListener("mousedown", (e) => e.preventDefault());
    lista.addEventListener("click", (e) => {
      const li = /** @type {HTMLElement} */ (e.target).closest("[role='option']");
      if (!li) return;
      this.escolher(Number(/** @type {HTMLElement} */ (li).dataset.indice));
      gatilho.focus();
    });
    // Mudança vinda de fora (reset do formulário, outro script): o botão acompanha.
    select.addEventListener("change", () => this.atualizarGatilho());
  }

  get aberta() {
    return Boolean(this.lista && !this.lista.hidden);
  }

  atualizarGatilho() {
    const select = /** @type {HTMLSelectElement} */ (this.select);
    const opcao = select.selectedOptions[0];
    /** @type {HTMLElement} */ (this.valor).textContent = opcao?.textContent?.trim() || "";
    this.gatilho?.classList.toggle("seletor__gatilho--vazio", !select.value);
  }

  abrir() {
    const select = /** @type {HTMLSelectElement} */ (this.select);
    const lista = /** @type {HTMLUListElement} */ (this.lista);
    lista.replaceChildren(
      ...Array.from(select.options).map((o, i) => {
        const li = document.createElement("li");
        li.id = `${lista.id}-${i}`;
        li.className = `combobox__opcao${o.selected ? " combobox__opcao--atual" : ""}`;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        if (o.disabled) li.setAttribute("aria-disabled", "true");
        li.dataset.indice = String(i);
        li.textContent = o.textContent?.trim() || "";
        return li;
      }),
    );
    lista.hidden = false;
    this.gatilho?.setAttribute("aria-expanded", "true");
    this.destacar(Math.max(0, select.selectedIndex));
    abrirEspaco(lista);
  }

  fechar() {
    if (!this.lista || this.lista.hidden) return;
    this.lista.hidden = true;
    this.gatilho?.setAttribute("aria-expanded", "false");
    this.gatilho?.removeAttribute("aria-activedescendant");
  }

  /** @param {number} indice */
  destacar(indice) {
    const opcoes = Array.from(this.lista?.children || []);
    if (opcoes.length === 0) return;
    this.ativo = Math.max(0, Math.min(opcoes.length - 1, indice));
    opcoes.forEach((li, i) => {
      li.setAttribute("aria-selected", String(i === this.ativo));
      if (i === this.ativo) {
        this.gatilho?.setAttribute("aria-activedescendant", li.id);
        li.scrollIntoView({ block: "nearest" });
      }
    });
  }

  /** @param {number} indice */
  escolher(indice) {
    const select = /** @type {HTMLSelectElement} */ (this.select);
    const opcao = select.options[indice];
    if (opcao && !opcao.disabled && select.selectedIndex !== indice) {
      select.selectedIndex = indice;
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    this.fechar();
  }

  /** Digitar letras salta para a opção que começa com elas. @param {string} letra */
  saltar(letra) {
    window.clearTimeout(this.atrasoBusca);
    this.busca += letra;
    this.atrasoBusca = window.setTimeout(() => { this.busca = ""; }, 600);
    const textos = Array.from(/** @type {HTMLSelectElement} */ (this.select).options)
      .map((o) => normalizar(o.textContent || ""));
    const termo = normalizar(this.busca);
    const inicio = this.aberta ? this.ativo + (this.busca.length === 1 ? 1 : 0) : 0;
    const ordem = [...textos.keys()].map((i) => (i + inicio) % textos.length);
    const achado = ordem.find((i) => textos[i].startsWith(termo));
    if (achado === undefined) return;
    if (!this.aberta) this.abrir();
    this.destacar(achado);
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    const total = /** @type {HTMLSelectElement} */ (this.select).options.length;
    if (!this.aberta) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        this.abrir();
      } else if (e.key === "Home" || e.key === "End") {
        e.preventDefault();
        this.abrir();
        this.destacar(e.key === "Home" ? 0 : total - 1);
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        this.saltar(e.key);
      }
      return;
    }
    /** @type {Record<string, number>} */
    const destino = {
      ArrowDown: this.ativo + 1, ArrowUp: this.ativo - 1, Home: 0, End: total - 1,
      PageDown: this.ativo + 10, PageUp: this.ativo - 10,
    };
    if (e.key in destino && !e.altKey) {
      e.preventDefault();
      this.destacar(destino[e.key]);
    } else if (e.key === "Enter" || (e.key === " " && !this.busca) || (e.key === "ArrowUp" && e.altKey)) {
      e.preventDefault();
      this.escolher(this.ativo);
    } else if (e.key === "Tab") {
      this.escolher(this.ativo);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      this.fechar();
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
      this.saltar(e.key);
    }
  }
}

customElements.define("pc-select", PcSelect);
