// @ts-check
/**
 * <pc-multiescolha> — vários registros escolhidos por busca (ex.: motoristas habituais).
 *
 * Por dentro: um <pc-combobox> remoto (busca) e a lista dos escolhidos, cada um com um
 * <input type="hidden" name="{data-nome}">. Escolher na busca acrescenta uma linha (sem
 * repetir); "Remover" tira. O servidor desenha os já escolhidos e valida tudo de novo.
 *
 * Variantes em cartões (`data-variante`): "equipe" (pessoas, com as iniciais) e "oficios"
 * (os ofícios que o documento junta, com o ícone do documento). Acrescentar avisa quem
 * depende da escolha com `pc-escolhido` (ex.: o termo preenche os campos com os ofícios).
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

  /** @param {{id: string, titulo: string, meta?: string, unidade?: string}} opcao */
  adicionar(opcao) {
    if (!this.lista || !opcao?.id) return;
    if (this.lista.querySelector(`[data-id="${CSS.escape(String(opcao.id))}"]`)) {
      this.anunciar(`${opcao.titulo} já está na lista.`);
      return;
    }
    if (this.emCartoes) {
      // Um só (quem dirige, no lote): escolher outro troca o escolhido.
      const maximo = Number(this.dataset.maximo || 0);
      if (maximo && this.lista.children.length >= maximo) this.lista.firstElementChild?.remove();
      this.lista.append(this.cartaoDeEquipe(opcao));
      this.sincronizar();
      this.anunciar(`${opcao.titulo} adicionado.`);
      this.dispatchEvent(new CustomEvent("pc-escolhido", { bubbles: true, detail: opcao }));
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

  /** O cartão de pessoa da equipe do ofício (viagens/oficios/_equipe.html e
   * viagens/widgets/equipe.html): iniciais no avatar, nome, cargo e lotação, e o X.
   * `data-servidor/unidade/nome/motorista` são o que <pc-transporte> lê para sugerir a viatura.
   * @param {{id: string, titulo: string, meta?: string, unidade?: string}} opcao */
  cartaoDeEquipe(opcao) {
    const oficio = this.dataset.variante === "oficios";
    const item = document.createElement("li");
    item.className = "pessoa equipe__cartao multiescolha__item";
    item.dataset.id = String(opcao.id);
    item.dataset.servidor = String(opcao.id);
    item.dataset.unidade = opcao.unidade || "";
    item.dataset.nome = opcao.titulo;
    const dirige = this.hasAttribute("data-motorista");
    if (dirige) item.setAttribute("data-motorista", "");
    const oculto = document.createElement("input");
    oculto.type = "hidden";
    oculto.name = this.dataset.nome || "";
    oculto.value = String(opcao.id);
    const avatar = document.createElement("span");
    avatar.className = dirige ? "avatar avatar--escuro" : "avatar";
    avatar.setAttribute("aria-hidden", "true");
    if (oficio) {
      avatar.append(icone("file-text", "icone icone--sm"));
    } else {
      // Como Servidor.iniciais: primeira e última palavra com mais de duas letras.
      const palavras = opcao.titulo.split(/\s+/).filter(Boolean);
      const longas = palavras.filter((p) => p.length > 2);
      const base = longas.length ? longas : palavras;
      avatar.textContent = (base[0]?.[0] || "") + (base.length > 1 ? base[base.length - 1][0] : "");
      avatar.textContent = avatar.textContent.toUpperCase();
    }
    const texto = document.createElement("span");
    texto.className = "pessoa__texto";
    const nome = document.createElement("span");
    nome.className = "pessoa__nome";
    nome.textContent = opcao.titulo;
    const meta = document.createElement("span");
    meta.className = "pessoa__meta";
    meta.textContent = opcao.meta || (oficio ? "" : "Cadastro incompleto");
    texto.append(nome, meta);
    const acoes = document.createElement("span");
    acoes.className = "equipe__acoes";
    const remover = document.createElement("button");
    remover.type = "button";
    remover.className = "equipe__acao equipe__acao--remover";
    remover.dataset.remover = "";
    remover.setAttribute("aria-label", oficio ? `Desvincular ${opcao.titulo}` : `Remover ${opcao.titulo} da equipe`);
    remover.title = oficio ? "Desvincular" : "Remover da equipe";
    remover.append(icone("x", "icone icone--sm"));
    acoes.append(remover);
    item.append(oculto, avatar, texto, acoes);
    return item;
  }

  /** Escolhidos em cartões (equipe, ofícios), na grade que fecha a linha. */
  get emCartoes() {
    return this.dataset.variante === "equipe" || this.dataset.variante === "oficios";
  }

  sincronizar() {
    if (this.vazio && this.lista) this.vazio.hidden = this.lista.children.length > 0;
    if (this.emCartoes) this.arrumarEquipe();
    if (this.dataset.variante === "equipe") {
      // A viatura acompanha a equipe (<pc-transporte>: sugestões, chips, quem dirige).
      this.dispatchEvent(new CustomEvent("pc-equipe-alterada", { bubbles: true }));
    }
    // Acrescentar ou tirar não é digitação: avisa o formulário (autosave, proteção de saída).
    this.entrada?.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /** Equipe: a grade que fecha a linha (como larguras_de_cartoes, no servidor) e a busca
   * sem quem já está escolhido. */
  arrumarEquipe() {
    if (!this.lista) return;
    const cartoes = [...this.lista.children];
    /** @type {number[]} */
    const larguras = [];
    for (let restante = cartoes.length; restante > 0;) {
      const porLinha = restante === 4 ? 2 : Math.min(3, restante);
      for (let i = 0; i < porLinha; i++) larguras.push(6 / porLinha);
      restante -= porLinha;
    }
    cartoes.forEach((cartao, i) => {
      cartao.classList.remove("resumo__cartao--2", "resumo__cartao--3", "resumo__cartao--6");
      cartao.classList.add(`resumo__cartao--${larguras[i]}`);
    });
    const busca = /** @type {HTMLElement | null} */ (this.querySelector("pc-combobox[data-fonte-base]"));
    if (busca) {
      const ids = cartoes.map((c) => /** @type {HTMLElement} */ (c).dataset.id).join(",");
      busca.dataset.fonte = `${busca.dataset.fonteBase}?excluir=${ids}&q=`;
    }
  }

  /** @param {string} texto */
  anunciar(texto) {
    if (this.anuncio) this.anuncio.textContent = texto;
  }
}

customElements.define("pc-multiescolha", PcMultiescolha);
