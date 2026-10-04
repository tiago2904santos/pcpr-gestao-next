// @ts-check
/**
 * <pc-linhas> — linhas repetidas de um formulário (ex.: o efetivo do plano: unidade, cargo,
 * quantidade). "Adicionar linha" clona o <template data-modelo> (os "__n__" de id, for e
 * aria viram um número novo); o botão de cada linha a remove — a última só se esvazia, para
 * a tela nunca ficar sem onde digitar. Cada mudança avisa o formulário (autosave e
 * proteção de saída) e é anunciada a quem usa leitor de tela.
 *
 * Sem JavaScript as linhas desenhadas pelo servidor continuam funcionando; só não se
 * acrescentam novas.
 */

export class PcLinhas extends HTMLElement {
  /** Quantas linhas já foram criadas (dá o número dos ids novos). */
  contador = 0;
  /** Como a linha se chama nos anúncios ("linha do efetivo"). */
  rotulo = "linha";

  connectedCallback() {
    if (this.dataset.pronto) return;
    this.dataset.pronto = "1";
    this.lista = /** @type {HTMLElement | null} */ (this.querySelector("[data-lista]"));
    this.modelo = /** @type {HTMLTemplateElement | null} */ (this.querySelector("template[data-modelo]"));
    this.anuncio = /** @type {HTMLElement | null} */ (this.querySelector("[data-anuncio]"));
    this.contador = this.lista ? this.lista.children.length : 0;
    this.rotulo = this.dataset.rotulo || "linha";
    this.addEventListener("click", (evento) => {
      const alvo = /** @type {HTMLElement} */ (evento.target);
      if (alvo.closest("[data-adicionar]")) {
        this.adicionar();
        return;
      }
      const remover = alvo.closest("[data-remover-linha]");
      const linha = /** @type {HTMLElement | null} */ (remover?.closest("[data-linha]") ?? null);
      if (linha) this.remover(linha);
    });
  }

  adicionar() {
    if (!this.lista || !this.modelo) return;
    this.contador += 1;
    const numero = String(this.contador);
    const fragmento = /** @type {DocumentFragment} */ (this.modelo.content.cloneNode(true));
    fragmento.querySelectorAll("*").forEach((el) => {
      for (const atributo of ["id", "for", "aria-labelledby", "aria-describedby", "aria-label"]) {
        const valor = el.getAttribute(atributo);
        if (valor && valor.includes("__n__")) el.setAttribute(atributo, valor.replaceAll("__n__", numero));
      }
    });
    const linha = /** @type {HTMLElement} */ (fragmento.firstElementChild);
    this.lista.append(fragmento);
    this.renumerar();
    if (linha) this.primeiroCampo(linha)?.focus();
    this.anunciar(`${this.capitalizar(this.rotulo)} ${this.lista.children.length} adicionada.`);
    this.avisarFormulario();
  }

  /** @param {HTMLElement} linha */
  remover(linha) {
    if (!this.lista) return;
    const linhas = [...this.lista.children];
    const posicao = linhas.indexOf(linha);
    if (linhas.length === 1) {
      // A última linha só se esvazia: sempre há onde digitar.
      linha.querySelectorAll("select").forEach((s) => { /** @type {HTMLSelectElement} */ (s).value = ""; });
      linha.querySelectorAll("input:not([type='hidden'])").forEach((i) => {
        const campo = /** @type {HTMLInputElement} */ (i);
        campo.value = campo.dataset.padrao ?? "";
      });
      this.anunciar(`${this.capitalizar(this.rotulo)} esvaziada.`);
    } else {
      linha.remove();
      this.renumerar();
      this.anunciar(`${this.capitalizar(this.rotulo)} ${posicao + 1} removida.`);
    }
    const restantes = [...this.lista.children];
    const foco = restantes[Math.min(posicao, restantes.length - 1)];
    /** @type {HTMLElement | null} */ ((foco && this.primeiroCampo(/** @type {HTMLElement} */ (foco)))
      ?? this.querySelector("[data-adicionar]"))?.focus();
    this.avisarFormulario();
  }

  /** O primeiro controle visível da linha (a lista própria esconde o <select> nativo e
   * mostra o botão dela). @param {HTMLElement} linha @returns {HTMLElement | null} */
  primeiroCampo(linha) {
    const candidatos = /** @type {HTMLElement[]} */ ([...linha.querySelectorAll(
      "select, input:not([type='hidden']), button:not([data-remover-linha])")]);
    return candidatos.find((el) => !el.hidden && el.getAttribute("aria-hidden") !== "true") ?? null;
  }

  /** Os botões de remover dizem qual linha removem ("Remover a linha 2"). */
  renumerar() {
    if (!this.lista) return;
    [...this.lista.children].forEach((linha, i) => {
      linha.querySelector("[data-remover-linha]")?.setAttribute(
        "aria-label", `Remover a ${this.rotulo} ${i + 1}`);
    });
  }

  /** Mudança sem digitação (linha nova ou removida): o formulário precisa saber. */
  avisarFormulario() {
    const marcador = this.querySelector("input[type='hidden']");
    marcador?.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /** @param {string} texto */
  capitalizar(texto) {
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  /** @param {string} texto */
  anunciar(texto) {
    if (this.anuncio) this.anuncio.textContent = texto;
  }
}

customElements.define("pc-linhas", PcLinhas);
