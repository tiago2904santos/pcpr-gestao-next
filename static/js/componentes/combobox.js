// @ts-check
/**
 * <pc-combobox> — campo de busca com lista de sugestões (WAI-ARIA combobox 1.2).
 *
 * Dois modos:
 *  1. Aprimoramento de <select>: o <select> interno continua sendo o valor do
 *     formulário (funciona sem JS); o componente oferece busca por digitação.
 *  2. Remoto (`data-fonte="/url?q="`): consulta JSON [{id, titulo, meta}] e
 *     emite `pc-selecionado` (detail = opção). Com `data-acao-url`, envia
 *     POST via HTMX ({id}) e troca `data-alvo` pelo HTML retornado — o
 *     servidor continua sendo a fonte da verdade.
 */

/** @typedef {{id: string, titulo: string, meta?: string}} Opcao */

let contador = 0;

/** @param {string} t */
const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export class PcCombobox extends HTMLElement {
  /** @type {Opcao[]} */
  opcoes = [];
  ativo = -1;
  /** Quem digitou já quer a primeira sugestão pronta; quem só abriu a lista, não. */
  primeiroPronto = false;
  /** @type {HTMLButtonElement | null} */
  limparBotao = null;

  connectedCallback() {
    if (this.dataset.pronto) return;
    this.dataset.pronto = "1";
    contador += 1;
    const base = `cbx-${contador}`;
    this.select = /** @type {HTMLSelectElement | null} */ (this.querySelector("select"));
    this.entrada = /** @type {HTMLInputElement | null} */ (
      this.querySelector("input[role='combobox']") ||
        (this.dataset.fonte ? this.querySelector("input:not([type='hidden'])") : null)
    );
    if (this.entrada) this.entrada.setAttribute("role", "combobox");
    if (this.select && !this.entrada) this.criarEntradaParaSelect();
    if (!this.entrada) return;

    this.lista = document.createElement("ul");
    this.lista.className = "combobox__lista";
    this.lista.id = `${base}-lista`;
    this.lista.setAttribute("role", "listbox");
    this.lista.hidden = true;
    this.anuncio = document.createElement("div");
    this.anuncio.className = "sr-only";
    this.anuncio.setAttribute("aria-live", "polite");
    this.append(this.lista, this.anuncio);

    this.entrada.setAttribute("aria-controls", this.lista.id);
    this.entrada.setAttribute("aria-expanded", "false");
    this.entrada.setAttribute("aria-autocomplete", "list");
    this.entrada.autocomplete = "off";
    this.criarLimpar();

    /** @type {number | undefined} */
    this.atraso = undefined;
    /** @type {AbortController | null} */
    this.pedido = null;

    this.entrada.addEventListener("input", () => this.aoDigitar());
    this.entrada.addEventListener("focus", () => {
      if (!this.dataset.fonte) this.filtrarLocal();
    });
    // Valor posto de fora (herdado de outro modo, preenchido pelo servidor): só acerta o "limpar".
    this.entrada.addEventListener("change", () => this.sincronizarLimpar());
    this.entrada.addEventListener("keydown", (e) => this.teclado(e));
    this.entrada.addEventListener("blur", () => window.setTimeout(() => this.fechar(), 120));
    this.lista.addEventListener("mousedown", (e) => e.preventDefault());
    this.lista.addEventListener("click", (e) => {
      const li = /** @type {HTMLElement} */ (e.target).closest("[role='option']");
      if (li) this.escolher(Number(/** @type {HTMLElement} */ (li).dataset.indice));
    });
  }

  /**
   * Botão "limpar" dentro do campo: trocar de município não exige apagar letra por letra.
   * Só aparece quando há texto, então não cria parada no Tab em campo vazio.
   */
  criarLimpar() {
    const entrada = /** @type {HTMLInputElement} */ (this.entrada);
    let caixa = entrada.parentElement;
    if (!caixa || !caixa.classList.contains("entrada-composta")) {
      caixa = document.createElement("div");
      caixa.className = "entrada-composta";
      entrada.before(caixa);
      caixa.append(entrada);
    }
    caixa.classList.add("entrada-composta--limpavel");
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "entrada-composta__botao";
    botao.title = "Limpar o campo";
    botao.hidden = true;
    const rotulo = document.createElement("span");
    rotulo.className = "sr-only";
    rotulo.textContent = "Limpar o campo";
    botao.append(this.iconeX(), rotulo);
    botao.addEventListener("click", () => this.limpar());
    caixa.append(botao);
    this.limparBotao = botao;
    this.sincronizarLimpar();
  }

  /** Ícone do sprite já carregado pela página. */
  iconeX() {
    const uso = document.querySelector("svg.icone use")?.getAttribute("href") || "";
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icone");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `${uso.split("#")[0]}#i-x`);
    svg.append(use);
    return svg;
  }

  sincronizarLimpar() {
    if (this.limparBotao) this.limparBotao.hidden = !this.entrada?.value.trim();
  }

  limpar() {
    if (!this.entrada) return;
    this.entrada.value = "";
    // Os mesmos eventos de quem apaga à mão: o <select> volta a vazio e a tela recalcula.
    this.entrada.dispatchEvent(new Event("input", { bubbles: true }));
    this.entrada.dispatchEvent(new Event("change", { bubbles: true }));
    this.entrada.focus();
    this.sincronizarLimpar();
  }

  criarEntradaParaSelect() {
    const select = /** @type {HTMLSelectElement} */ (this.select);
    const entrada = document.createElement("input");
    entrada.type = "text";
    entrada.className = "entrada";
    entrada.setAttribute("role", "combobox");
    entrada.id = select.id ? `${select.id}-busca` : "";
    const rotulo = select.id ? document.querySelector(`label[for='${select.id}']`) : null;
    if (rotulo && entrada.id) rotulo.setAttribute("for", entrada.id);
    if (select.getAttribute("aria-describedby")) {
      entrada.setAttribute("aria-describedby", select.getAttribute("aria-describedby") || "");
    }
    if (select.getAttribute("aria-invalid")) entrada.setAttribute("aria-invalid", "true");
    entrada.placeholder = this.dataset.placeholder || "Digite para buscar…";
    const atual = select.selectedOptions[0];
    if (atual && atual.value) entrada.value = atual.textContent?.trim() || "";
    entrada.required = select.required;
    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.required = false;
    select.after(entrada);
    this.entrada = entrada;
  }

  aoDigitar() {
    this.sincronizarLimpar();
    if (this.select && this.entrada && this.entrada.value.trim() === "") {
      this.select.value = "";
      this.select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    window.clearTimeout(this.atraso);
    if (this.dataset.fonte) {
      this.atraso = window.setTimeout(() => this.buscarRemoto(), 180);
    } else {
      this.filtrarLocal();
    }
  }

  filtrarLocal() {
    if (!this.select || !this.entrada) return;
    const termo = normalizar(this.entrada.value.trim());
    const atualTexto = this.select.selectedOptions[0]?.textContent?.trim() || "";
    const mostrarTudo = termo === "" || this.entrada.value.trim() === atualTexto;
    this.opcoes = Array.from(this.select.options)
      .filter((o) => o.value && (mostrarTudo || normalizar(o.textContent || "").includes(termo)))
      .slice(0, 50)
      .map((o) => ({ id: o.value, titulo: o.textContent?.trim() || "", meta: o.dataset.meta }));
    this.primeiroPronto = !mostrarTudo;
    this.renderizar();
  }

  async buscarRemoto() {
    if (!this.entrada) return;
    const termo = this.entrada.value.trim();
    const minimo = Number(this.dataset.minimo || 2);
    if (termo.length < minimo) {
      this.opcoes = [];
      this.fechar();
      return;
    }
    this.pedido?.abort();
    this.pedido = new AbortController();
    this.setAttribute("aria-busy", "true");
    try {
      const resposta = await fetch(`${this.dataset.fonte}${encodeURIComponent(termo)}`, {
        signal: this.pedido.signal,
        headers: { Accept: "application/json" },
      });
      const dados = await resposta.json();
      this.opcoes = dados.resultados || [];
      this.primeiroPronto = true;
      this.renderizar();
    } catch (erro) {
      if (/** @type {Error} */ (erro).name !== "AbortError") {
        this.opcoes = [];
        this.primeiroPronto = false;
        this.renderizar("Não foi possível buscar agora. Tente novamente.");
      }
    } finally {
      this.removeAttribute("aria-busy");
    }
  }

  /** @param {string} [mensagemVazia] */
  renderizar(mensagemVazia) {
    if (!this.lista || !this.entrada) return;
    this.lista.replaceChildren();
    this.ativo = -1;
    if (this.opcoes.length === 0) {
      const vazio = document.createElement("li");
      vazio.className = "combobox__vazio";
      vazio.textContent = mensagemVazia || "Nenhum resultado. Confira a grafia ou o cadastro.";
      this.lista.append(vazio);
    }
    this.opcoes.forEach((o, i) => {
      const li = document.createElement("li");
      li.id = `${this.lista?.id}-op-${i}`;
      li.className = "combobox__opcao";
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", "false");
      li.dataset.indice = String(i);
      const textos = document.createElement("div");
      const titulo = document.createElement("div");
      titulo.className = "combobox__opcao-titulo";
      titulo.textContent = o.titulo;
      textos.append(titulo);
      if (o.meta) {
        const meta = document.createElement("div");
        meta.className = "combobox__opcao-meta";
        meta.textContent = o.meta;
        textos.append(meta);
      }
      li.append(textos);
      this.lista?.append(li);
    });
    this.lista.hidden = false;
    this.entrada.setAttribute("aria-expanded", "true");
    if (this.anuncio) {
      const n = this.opcoes.length;
      this.anuncio.textContent = n === 0 ? "Nenhum resultado." : `${n} resultado${n > 1 ? "s" : ""}.`;
    }
    // Buscou escrevendo: a primeira já fica escolhida, então digitar e dar Enter basta.
    if (this.primeiroPronto && this.opcoes.length) this.destacar(0);
  }

  fechar() {
    if (!this.lista || !this.entrada) return;
    this.lista.hidden = true;
    this.entrada.setAttribute("aria-expanded", "false");
    this.entrada.removeAttribute("aria-activedescendant");
  }

  /** @param {number} indice */
  destacar(indice) {
    if (!this.lista || !this.entrada || this.opcoes.length === 0) return;
    this.ativo = (indice + this.opcoes.length) % this.opcoes.length;
    this.lista.querySelectorAll("[role='option']").forEach((li, i) => {
      li.setAttribute("aria-selected", String(i === this.ativo));
      if (i === this.ativo) {
        this.entrada?.setAttribute("aria-activedescendant", li.id);
        li.scrollIntoView({ block: "nearest" });
      }
    });
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    const aberta = this.lista && !this.lista.hidden;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (!aberta) this.dataset.fonte ? this.buscarRemoto() : this.filtrarLocal();
        else this.destacar(this.ativo + 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (aberta) this.destacar(this.ativo - 1);
        break;
      case "Enter":
        if (aberta && this.ativo >= 0) {
          e.preventDefault();
          this.escolher(this.ativo);
        }
        break;
      case "Escape":
        if (aberta) {
          e.preventDefault();
          this.fechar();
        }
        break;
      default:
        break;
    }
  }

  /** @param {number} indice */
  escolher(indice) {
    const opcao = this.opcoes[indice];
    if (!opcao || !this.entrada) return;
    if (this.select) {
      this.select.value = opcao.id;
      this.select.dispatchEvent(new Event("change", { bubbles: true }));
      this.entrada.value = opcao.titulo;
    } else if (this.hasAttribute("data-valor-texto")) {
      // Modo "texto": o próprio campo é o valor (ex.: "Arapongas/PR"), validado no servidor.
      this.entrada.value = opcao.titulo;
      this.entrada.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      this.entrada.value = "";
    }
    this.fechar();
    this.sincronizarLimpar();
    this.dispatchEvent(new CustomEvent("pc-selecionado", { detail: opcao, bubbles: true }));
    const url = this.dataset.acaoUrl;
    const htmx = /** @type {any} */ (window).htmx;
    if (url && htmx) {
      htmx.ajax("POST", url, {
        source: this,
        target: this.dataset.alvo || undefined,
        swap: this.dataset.troca || "outerHTML",
        values: { id: opcao.id },
      });
    }
  }
}

customElements.define("pc-combobox", PcCombobox);
