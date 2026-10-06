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
 *     servidor continua sendo a fonte da verdade. Com um
 *     `<input type="hidden" data-valor-id>` dentro, o id escolhido vai para ele (campo de
 *     formulário, ex.: um servidor) e o texto visível mostra o título; digitar de novo
 *     limpa o id, para nunca enviar um valor que não corresponde ao que está escrito.
 */

import { adicionarLimpar } from "./limpar.js";
import { posicionar, recolher, soltar } from "./painel-flutuante.js";

/** @typedef {{id: string, titulo: string, meta?: string, chips?: string[], grupo?: string}} Opcao */

let contador = 0;

/** @param {string} t */
const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export class PcCombobox extends HTMLElement {
  /** @type {HTMLCanvasElement | undefined} Régua de texto (mede o nome para o detalhe). */
  static regua;
  /** @type {Opcao[]} */
  opcoes = [];
  ativo = -1;
  /** Quem digitou já quer a primeira sugestão pronta; quem só abriu a lista, não. */
  primeiroPronto = false;
  /** @type {(() => void) | undefined} */
  sincronizarBotao = undefined;
  /** Mudança do <select> disparada por este componente (não precisa reler o texto). */
  escolhendo = false;

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
    this.prepararMeta();

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
    if (this.select) {
      this.select.addEventListener("change", () => {
        if (this.escolhendo || !this.select || !this.entrada) return;
        const atual = this.select.selectedOptions[0];
        const mostrar = atual && (atual.value || this.hasAttribute("data-vazio-e-valor"));
        this.entrada.value = mostrar ? atual.textContent?.trim() || "" : "";
        this.sincronizarLimpar();
      });
    }
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
  /** Botão × do campo, igual ao das buscas (componentes/limpar.js). */
  criarLimpar() {
    const entrada = /** @type {HTMLInputElement} */ (this.entrada);
    this.sincronizarBotao = adicionarLimpar(entrada, () => this.aoDigitar());
  }

  sincronizarLimpar() {
    this.sincronizarBotao?.();
  }

  /**
   * `data-mostrar-meta="cargo"` + um `[data-meta-escolhida]` dentro da caixa: o detalhe da
   * opção escolhida (ex.: o cargo do servidor) aparece dentro do campo, logo depois do nome.
   * A posição acompanha a largura do nome (medida com a fonte do campo).
   */
  prepararMeta() {
    this.meta = /** @type {HTMLElement | null} */ (this.querySelector("[data-meta-escolhida]"));
    if (!this.meta || !this.entrada) return;
    new ResizeObserver(() => this.posicionarMeta()).observe(this.entrada);
    document.fonts?.ready.then(() => this.posicionarMeta());
  }

  /** @param {string} texto */
  mostrarMeta(texto) {
    if (!this.meta) return;
    this.meta.textContent = texto;
    this.meta.hidden = !texto;
    this.posicionarMeta();
  }

  posicionarMeta() {
    const entrada = this.entrada;
    if (!this.meta || this.meta.hidden || !entrada) return;
    const estilo = getComputedStyle(entrada);
    const tela = (PcCombobox.regua ??= document.createElement("canvas")).getContext("2d");
    if (!tela) return;
    tela.font = `${estilo.fontWeight} ${estilo.fontSize} ${estilo.fontFamily}`;
    const x = entrada.offsetLeft + parseFloat(estilo.paddingLeft) + tela.measureText(entrada.value).width;
    this.meta.style.setProperty("--meta-x", `${Math.round(x)}px`);
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
    // `data-vazio-e-valor`: a escolha vazia é um valor de verdade (ex.: "quem assina" = o da
    // configuração) — o nome dela aparece no campo, em vez do campo em branco.
    const vazioEValor = this.hasAttribute("data-vazio-e-valor");
    if (atual && (atual.value || vazioEValor)) entrada.value = atual.textContent?.trim() || "";
    entrada.required = select.required;
    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.required = false;
    select.after(entrada);
    this.entrada = entrada;
  }

  /** @returns {HTMLInputElement | null} */
  get oculto() {
    return this.querySelector("input[type='hidden'][data-valor-id]");
  }

  aoDigitar() {
    this.sincronizarLimpar();
    this.mostrarMeta("");
    const oculto = this.oculto;
    if (oculto && oculto.value) {
      oculto.value = "";
      oculto.dispatchEvent(new Event("change", { bubbles: true }));
    }
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
      .map((o) => ({
        id: o.value,
        titulo: o.textContent?.trim() || "",
        meta: o.dataset.meta,
        // Sugestões (ex.: viaturas da unidade da equipe): chips ao lado do título e um
        // cabeçalho de grupo quando a lista muda de "Sugeridas" para "Outras".
        chips: o.dataset.chips ? o.dataset.chips.split("|").filter(Boolean) : undefined,
        grupo: o.dataset.grupo,
      }));
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
    let grupoAnterior = "";
    this.opcoes.forEach((o, i) => {
      if (o.grupo && o.grupo !== grupoAnterior) {
        const cabecalho = document.createElement("li");
        cabecalho.className = "combobox__grupo";
        cabecalho.setAttribute("role", "presentation");
        cabecalho.textContent = o.grupo;
        this.lista?.append(cabecalho);
      }
      grupoAnterior = o.grupo || grupoAnterior;
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
      for (const chip of o.chips || []) {
        const selo = document.createElement("span");
        selo.className = "selo selo--info selo--sem-ponto combobox__chip";
        selo.textContent = chip;
        titulo.append(" ", selo);
      }
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
    // Dentro de um <dialog> a lista vai para a camada de topo (não é cortada pela janela).
    soltar(this.lista, this.entrada);
    posicionar(this.lista, this.entrada);
    if (this.anuncio) {
      const n = this.opcoes.length;
      this.anuncio.textContent = n === 0 ? "Nenhum resultado." : `${n} resultado${n > 1 ? "s" : ""}.`;
    }
    // Buscou escrevendo: a primeira já fica escolhida, então digitar e dar Enter basta.
    if (this.primeiroPronto && this.opcoes.length) this.destacar(0);
  }

  fechar() {
    if (!this.lista || !this.entrada) return;
    recolher(this.lista);
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
      this.escolhendo = true;
      this.select.value = opcao.id;
      this.select.dispatchEvent(new Event("change", { bubbles: true }));
      this.escolhendo = false;
      this.entrada.value = opcao.titulo;
    } else if (this.oculto) {
      const oculto = /** @type {HTMLInputElement} */ (this.oculto);
      oculto.value = opcao.id;
      oculto.dispatchEvent(new Event("change", { bubbles: true }));
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
    const campoMeta = /** @type {keyof Opcao} */ (this.dataset.mostrarMeta || "meta");
    this.mostrarMeta(String(opcao[campoMeta] ?? ""));
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
