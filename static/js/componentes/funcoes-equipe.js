// @ts-check
/**
 * Funções da equipe na OS (caminhão, micro-ônibus, cerimonial): o seletor de pílulas em cada
 * cartão da equipe (viagens/widgets/_funcao_escolha.html) e o resumo "quantos em cada função"
 * acima dos cartões.
 *
 * - Quem entra na equipe já ganha o seletor (o servidor o desenha para os gravados).
 * - Trocar o modelo troca as opções; a escolha que continua válida fica. Também mostra o
 *   período do evento (qualquer modelo) e o horário do briefing (modelos que o pedem).
 * - Clicar na função escolhida a desmarca (rádio nativo não desmarca sozinho).
 * As escolhas são rádios `funcao_<id>`: o formulário e o autosave as levam como qualquer campo.
 */

import { icone } from "./menu.js";

/** @typedef {{valor: string, rotulo: string, icone: string, dica: string}} Opcao */

class FuncoesDaEquipe {
  /** @param {HTMLElement} multi */
  constructor(multi) {
    this.multi = multi;
    /** @type {Record<string, Opcao[]>} */
    this.porTipo = JSON.parse(multi.dataset.funcoes || "{}");
    /** @type {string[]} ids dos modelos que pedem o horário do briefing */
    this.comHora = JSON.parse(multi.dataset.comHora || "[]");
    // O tipo do mesmo formulário (a página pode ter outro "id_tipo", como o da viatura).
    const id = CSS.escape(multi.dataset.campoTipo || "");
    this.campoTipo = /** @type {HTMLSelectElement | null} */ (
      (multi.closest("form") || document).querySelector(`select#${id}`));
    this.lista = multi.querySelector(".multiescolha__lista");
    this.resumo = /** @type {HTMLElement | null} */ (multi.querySelector("[data-funcoes-resumo]"));
    this.opcoes = this.opcoesDoTipo();

    multi.addEventListener("pc-equipe-alterada", () => this.atualizar(false));
    this.campoTipo?.addEventListener("change", () => {
      this.opcoes = this.opcoesDoTipo();
      this.atualizar(true);
      this.camposDoModelo();
    });
    // Desmarcar: o rádio já marcado, clicado de novo, volta para "sem função".
    multi.addEventListener("pointerdown", (evento) => {
      const rotulo = /** @type {HTMLElement} */ (evento.target).closest(".funcao-escolha__opcao");
      const radio = /** @type {HTMLInputElement | null} */ (rotulo?.querySelector("input") || null);
      if (radio) radio.dataset.estava = radio.checked ? "1" : "";
    });
    multi.addEventListener("click", (evento) => {
      const radio = /** @type {HTMLElement} */ (evento.target);
      if (!(radio instanceof HTMLInputElement) || !radio.classList.contains("funcao-escolha__radio")) return;
      if (radio.dataset.estava === "1") {
        radio.checked = false;
        radio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      radio.dataset.estava = "";
    });
    multi.addEventListener("change", (evento) => {
      if (/** @type {HTMLElement} */ (evento.target).classList?.contains("funcao-escolha__radio")) {
        this.resumir();
      }
    });
    this.atualizar(false);
  }

  /** O período do evento aparece com qualquer modelo; o horário, só nos que o pedem. */
  camposDoModelo() {
    const valor = this.campoTipo?.value || "";
    const form = this.multi.closest("form") || document;
    for (const el of form.querySelectorAll("[data-campo-evento]")) {
      /** @type {HTMLElement} */ (el).hidden = !valor;
    }
    for (const el of form.querySelectorAll("[data-campo-hora]")) {
      /** @type {HTMLElement} */ (el).hidden = !this.comHora.includes(valor);
    }
  }

  /** @returns {Opcao[]} */
  opcoesDoTipo() {
    return this.porTipo[this.campoTipo?.value || ""] || [];
  }

  /** @returns {HTMLElement[]} */
  get cartoes() {
    return this.lista ? /** @type {HTMLElement[]} */ ([...this.lista.children]) : [];
  }

  /** Põe (ou tira) o seletor em cada cartão; `trocouTipo` refaz os que já existem. */
  atualizar(trocouTipo = false) {
    for (const cartao of this.cartoes) {
      const atual = /** @type {HTMLElement | null} */ (cartao.querySelector("[data-funcao-escolha]"));
      if (!this.opcoes.length) {
        atual?.remove();
        continue;
      }
      if (atual && !trocouTipo) continue;
      const marcada = /** @type {HTMLInputElement | null} */ (atual?.querySelector("input:checked") || null);
      atual?.remove();
      cartao.append(this.seletor(cartao, marcada?.value || ""));
    }
    if (this.resumo) this.resumo.hidden = !this.opcoes.length;
    // A nota do cabeçalho do bloco diz como a equipe sai no documento.
    const nota = this.multi.closest(".secao__bloco")?.querySelector("[data-equipe-nota]");
    if (nota) nota.textContent = this.opcoes.length ? "sai com a função de cada um" : "sai agrupada por cargo";
    this.resumir();
  }

  /** O mesmo desenho de _funcao_escolha.html.
   * @param {HTMLElement} cartao @param {string} escolhida */
  seletor(cartao, escolhida) {
    const id = cartao.dataset.id || "";
    const grupo = document.createElement("fieldset");
    grupo.className = "funcao-escolha";
    grupo.dataset.funcaoEscolha = "";
    const legenda = document.createElement("legend");
    legenda.className = "sr-only";
    legenda.textContent = `Função de ${cartao.dataset.nome || ""}`;
    grupo.append(legenda);
    for (const opcao of this.opcoes) {
      const rotulo = document.createElement("label");
      rotulo.className = "funcao-escolha__opcao";
      rotulo.dataset.funcao = opcao.valor;
      rotulo.title = opcao.dica;
      const radio = document.createElement("input");
      radio.className = "funcao-escolha__radio";
      radio.type = "radio";
      radio.name = `funcao_${id}`;
      radio.value = opcao.valor;
      radio.checked = opcao.valor === escolhida;
      const texto = document.createElement("span");
      texto.className = "funcao-escolha__rotulo";
      texto.textContent = opcao.rotulo;
      rotulo.append(radio, icone(opcao.icone, "icone icone--sm"), texto);
      grupo.append(rotulo);
    }
    return grupo;
  }

  /** "Condução 1 · Técnico 1 · Apoio 2" e quantos ainda estão sem função. */
  resumir() {
    if (!this.resumo || !this.opcoes.length) return;
    const cartoes = this.cartoes;
    /** @type {Record<string, number>} */
    const contagem = {};
    let sem = 0;
    for (const cartao of cartoes) {
      const marcada = /** @type {HTMLInputElement | null} */ (cartao.querySelector(".funcao-escolha__radio:checked"));
      if (marcada) contagem[marcada.value] = (contagem[marcada.value] || 0) + 1;
      else sem += 1;
    }
    this.resumo.replaceChildren();
    for (const opcao of this.opcoes) {
      const item = document.createElement("span");
      item.className = "funcoes-resumo__item";
      item.dataset.funcao = opcao.valor;
      const n = contagem[opcao.valor] || 0;
      if (!n) item.dataset.vazia = "";
      const nome = document.createElement("span");
      nome.textContent = opcao.rotulo;
      const numero = document.createElement("strong");
      numero.className = "funcoes-resumo__numero";
      numero.textContent = String(n);
      item.append(icone(opcao.icone, "icone icone--sm"), nome, numero);
      this.resumo.append(item);
    }
    const pendente = document.createElement("span");
    pendente.className = "funcoes-resumo__pendente";
    if (!cartoes.length) {
      pendente.textContent = "Adicione a equipe e escolha a função de cada um";
    } else if (sem) {
      pendente.dataset.aviso = "";
      pendente.append(icone("alert-circle", "icone icone--sm"),
        `${sem} sem função`);
    } else {
      pendente.append(icone("check", "icone icone--sm"), "Todos com função");
    }
    this.resumo.append(pendente);
  }
}

for (const multi of document.querySelectorAll("pc-multiescolha[data-funcoes]")) {
  const el = /** @type {HTMLElement} */ (multi);
  if (el.dataset.funcoesPronto) continue;
  el.dataset.funcoesPronto = "1";
  new FuncoesDaEquipe(el);
}

export {};
