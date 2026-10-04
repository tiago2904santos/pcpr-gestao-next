// @ts-check
/**
 * <pc-multiescolha> — vários registros escolhidos por busca (ex.: motoristas habituais).
 *
 * Por dentro: um <pc-combobox> remoto (busca) e a lista dos escolhidos, cada um com um
 * <input type="hidden" name="{data-nome}">. Escolher na busca acrescenta uma linha (sem
 * repetir); "Remover" tira. O servidor desenha os já escolhidos e valida tudo de novo.
 */

import { icone } from "./menu.js";

export class PcMultiescolha extends HTMLElement {
  connectedCallback() {
    if (this.dataset.pronto) return;
    this.dataset.pronto = "1";
    this.lista = /** @type {HTMLUListElement} */ (this.querySelector(".multiescolha__lista"));
    this.vazio = /** @type {HTMLElement | null} */ (this.querySelector(".multiescolha__vazio"));
    this.anuncio = /** @type {HTMLElement | null} */ (this.querySelector("[data-anuncio]"));
    this.entrada = /** @type {HTMLInputElement | null} */ (this.querySelector("input[role='combobox']"));
    this.addEventListener("pc-selecionado", (evento) => {
      evento.stopPropagation();
      this.adicionar(/** @type {CustomEvent} */ (evento).detail);
    });
    this.addEventListener("click", (evento) => {
      const botao = /** @type {HTMLElement} */ (evento.target).closest("[data-remover]");
      const item = botao?.closest(".multiescolha__item");
      if (!item) return;
      const nome = item.querySelector(".pessoa__nome")?.textContent || "";
      item.remove();
      this.sincronizar();
      this.anunciar(`${nome} removido.`);
      this.entrada?.focus();
    });
  }

  /** @param {{id: string, titulo: string, meta?: string}} opcao */
  adicionar(opcao) {
    if (!this.lista || !opcao?.id) return;
    if (this.lista.querySelector(`[data-id="${CSS.escape(String(opcao.id))}"]`)) {
      this.anunciar(`${opcao.titulo} já está na lista.`);
      return;
    }
    const item = document.createElement("li");
    item.className = "pessoa multiescolha__item";
    item.dataset.id = String(opcao.id);
    const oculto = document.createElement("input");
    oculto.type = "hidden";
    oculto.name = this.dataset.nome || "";
    oculto.value = String(opcao.id);
    const texto = document.createElement("span");
    texto.className = "pessoa__texto";
    const nome = document.createElement("span");
    nome.className = "pessoa__nome";
    nome.textContent = opcao.titulo;
    texto.append(nome);
    if (opcao.meta) {
      const meta = document.createElement("span");
      meta.className = "pessoa__meta";
      meta.textContent = opcao.meta;
      texto.append(meta);
    }
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "botao botao--icone botao--sutil botao--sm";
    remover.dataset.remover = "";
    remover.setAttribute("aria-label", `Remover ${opcao.titulo}`);
    remover.append(icone("x", "icone icone--sm"));
    item.append(oculto, texto, remover);
    this.lista.append(item);
    this.sincronizar();
    this.anunciar(`${opcao.titulo} adicionado.`);
  }

  sincronizar() {
    if (this.vazio && this.lista) this.vazio.hidden = this.lista.children.length > 0;
    // Acrescentar ou tirar não é digitação: avisa o formulário (autosave, proteção de saída).
    this.entrada?.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /** @param {string} texto */
  anunciar(texto) {
    if (this.anuncio) this.anuncio.textContent = texto;
  }
}

customElements.define("pc-multiescolha", PcMultiescolha);
