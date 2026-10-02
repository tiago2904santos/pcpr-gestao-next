// @ts-check
/**
 * Grava o formulário sozinho enquanto a pessoa preenche, para ninguém perder trabalho por
 * esquecer de salvar. Começa quando a primeira etapa está completa (o servidor decide o que
 * é "completa") e dali em diante repete a cada pausa na digitação.
 *
 * O que não é válido ainda não impede a gravada: o servidor guarda o que der, como rascunho.
 * Sem JavaScript nada muda — o botão "Salvar" continua sendo o caminho.
 *
 * Marcação: <form data-autosave="<url>"> com <input name="roteiro_id" data-roteiro-id>.
 * O status aparece em [data-status-salvamento].
 */

const ESPERA = 1200;

export class Autosave {
  /** @type {number | undefined} */
  atraso = undefined;
  /** @type {AbortController | null} */
  pedido = null;
  /** Última carga enviada, para não regravar o que não mudou. */
  ultima = "";

  /** @param {HTMLFormElement} form */
  constructor(form) {
    this.form = form;
    this.url = form.dataset.autosave || "";
    this.status = /** @type {HTMLElement | null} */ (document.querySelector("[data-status-salvamento]"));
    for (const evento of ["input", "change"]) {
      document.addEventListener(evento, (e) => {
        if (this.doFormulario(/** @type {Element} */ (e.target))) this.agendar();
      });
    }
    // Sair da página com algo por gravar: manda agora, sem esperar a pausa.
    window.addEventListener("pagehide", () => this.gravar(true));
  }

  /** @param {Element} alvo */
  doFormulario(alvo) {
    const campo = /** @type {HTMLInputElement} */ (alvo);
    return Boolean(campo.form === this.form
      || (campo.getAttribute && campo.getAttribute("form") === this.form.id));
  }

  agendar() {
    window.clearTimeout(this.atraso);
    this.atraso = window.setTimeout(() => this.gravar(), ESPERA);
  }

  /** @param {boolean} saindo */
  async gravar(saindo = false) {
    const dados = new FormData(this.form);
    const assinatura = new URLSearchParams(/** @type {any} */ (dados)).toString();
    if (assinatura === this.ultima) return;
    this.ultima = assinatura;
    if (saindo && navigator.sendBeacon) {
      navigator.sendBeacon(this.url, dados);
      return;
    }
    this.pedido?.abort();
    this.pedido = new AbortController();
    this.anunciar("Salvando…");
    try {
      const resposta = await fetch(this.url, { method: "POST", body: dados, signal: this.pedido.signal });
      if (!resposta.ok) throw new Error(String(resposta.status));
      const corpo = await resposta.json();
      if (!corpo.salvo) {
        this.ultima = "";  // tentar de novo na próxima mudança
        this.anunciar("Ainda não dá para salvar — complete a origem e um destino.");
        return;
      }
      const campoId = /** @type {HTMLInputElement | null} */ (this.form.querySelector("[data-roteiro-id]"));
      if (campoId && !campoId.value) campoId.value = String(corpo.id);
      this.anunciar(`Salvo automaticamente às ${corpo.em}`, true);
    } catch (erro) {
      if (/** @type {Error} */ (erro).name === "AbortError") return;
      this.ultima = "";
      this.anunciar("Não foi possível salvar agora — suas alterações continuam na tela.");
    }
  }

  /** @param {string} texto @param {boolean} ok */
  anunciar(texto, ok = false) {
    if (!this.status) return;
    this.status.textContent = texto;
    this.status.classList.toggle("barra-acoes__status--salvo", ok);
    this.status.classList.remove("barra-acoes__status--sujo");
  }
}

document.querySelectorAll("form[data-autosave]").forEach((f) => {
  new Autosave(/** @type {HTMLFormElement} */ (f));
});
