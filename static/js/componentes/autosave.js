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
 * O status aparece em [data-status-salvamento] (no [data-anuncio] dele, se houver): o de
 * dentro do formulário, quando a página tem vários (um por cartão, como na prestação de
 * contas), senão o da página.
 *
 * <form data-esperar-salvamento> (ações que não são do formulário, ex.: "Finalizar equipe")
 * espera as gravações pendentes de todos os formulários antes de enviar — sem isso, o envio
 * correria com o que ainda está para gravar.
 *
 * Depois de gravar, a tela acompanha o que foi gravado:
 *  - `campos` da resposta voltam ao formulário (ex.: a versão nova);
 *  - as regiões `[data-vivo][id]` (selos, conferência, listas que dependem dos dados) são
 *    trocadas pelas da página refeita no servidor — menos a que tem o foco — e a página
 *    refeita é anunciada (`pcpr:pagina-refeita`) para quem tem mais a refazer com ela;
 *  - `recarregar: true` (a gravação mudou CAMPOS, não só valores — ex.: funções da equipe
 *    a escolher) recarrega a página, já com tudo gravado.
 */

const ESPERA = 1200;

export class Autosave {
  /** @type {Autosave[]} todos os formulários da página que gravam sozinhos */
  static todos = [];
  /** @type {number | undefined} */
  atraso = undefined;
  /** Gravações em fila: uma por vez, cada uma com a versão que a anterior devolveu. */
  fila = Promise.resolve();
  /** Última carga enviada, para não regravar o que não mudou. */
  ultima = "";
  /** @type {Promise<void> | null} gravação automática em andamento */
  emVoo = null;
  /** O formulário está sendo enviado pelo botão (Salvar, Usar roteiro…). */
  enviando = false;
  /** A pessoa já mexeu em algo (até lá, o estado de partida pode ser reajustado). */
  mexeu = false;

  /** @param {HTMLFormElement} form */
  constructor(form) {
    this.form = form;
    this.url = form.dataset.autosave || "";
    this.status = /** @type {HTMLElement | null} */ (
      form.querySelector("[data-status-salvamento]") || document.querySelector("[data-status-salvamento]"));
    Autosave.todos.push(this);
    for (const evento of ["input", "change"]) {
      document.addEventListener(evento, (e) => {
        if (this.doFormulario(/** @type {Element} */ (e.target))) this.agendar();
      });
    }
    // Sair da página com algo por gravar: manda agora, sem esperar a pausa. Mas não quando
    // a saída é o próprio envio do formulário — o envio já leva tudo, e um segundo pedido com
    // a mesma versão seria acusado de conflito ("outra pessoa salvou…").
    window.addEventListener("pagehide", () => { if (!this.enviando) this.gravar(true); });
    form.addEventListener("submit", (e) => this.aoEnviar(/** @type {SubmitEvent} */ (e)));
    // O estado de partida é o que a página trouxe: sair sem mexer não grava nada (antes, a
    // saída gravava sempre — versão nova e evento vazio na trilha a cada visita). Os
    // componentes que se montam depois (seleções, buscas) podem ajustar campos ao carregar:
    // a partida é refeita no "load", se ninguém mexeu ainda.
    this.ultima = this.assinatura();
    window.addEventListener("load", () => { if (!this.mexeu) this.ultima = this.assinatura(); });
  }

  /** O formulário como texto (para saber se algo mudou desde a última gravação). */
  assinatura() {
    return new URLSearchParams(/** @type {any} */ (new FormData(this.form))).toString();
  }

  /** Envio pelo botão: cancela o que estava agendado e, se uma gravação automática está no
   * meio do caminho, espera ela voltar (com a versão nova) antes de enviar. @param {SubmitEvent} e */
  aoEnviar(e) {
    window.clearTimeout(this.atraso);
    if (this.enviando) return;
    if (!this.emVoo) {
      this.enviando = true;
      return;
    }
    e.preventDefault();
    const quem = e.submitter;
    this.emVoo.finally(() => {
      this.enviando = true;
      this.form.requestSubmit(/** @type {HTMLElement | null} */ (quem) ?? undefined);
    });
  }

  /** Grava agora o que está pendente e espera terminar (para quem vai enviar outra coisa). */
  async descarregar() {
    window.clearTimeout(this.atraso);
    await this.gravar();
    if (this.emVoo) await this.emVoo;
  }

  /** @param {Element} alvo */
  doFormulario(alvo) {
    const campo = /** @type {HTMLInputElement} */ (alvo);
    return Boolean(campo.form === this.form
      || (campo.getAttribute && campo.getAttribute("form") === this.form.id));
  }

  agendar() {
    this.mexeu = true;
    window.clearTimeout(this.atraso);
    this.atraso = window.setTimeout(() => this.gravar(), ESPERA);
  }

  /**
   * Põe a gravação na fila. Cancelar a que está no caminho não serve: o servidor já pode
   * ter gravado, e a seguinte iria com a versão velha — "outra pessoa alterou este termo".
   * Saindo da página não há fila: vai o que houver, de uma vez (sendBeacon).
   * @param {boolean} saindo
   */
  gravar(saindo = false) {
    if (saindo) return this.gravarAgora(true);
    this.fila = this.fila.then(() => this.gravarAgora()).catch(() => {});
    return this.fila;
  }

  /** @param {boolean} saindo */
  async gravarAgora(saindo = false) {
    const dados = new FormData(this.form);
    const assinatura = this.assinatura();
    if (assinatura === this.ultima) return;
    this.ultima = assinatura;
    if (saindo && navigator.sendBeacon) {
      navigator.sendBeacon(this.url, dados);
      return;
    }
    this.anunciar("Salvando…");
    /** @type {(valor?: void) => void} */
    let terminar = () => {};
    /** @type {Promise<void>} */
    const meu = new Promise((resolver) => { terminar = resolver; });
    this.emVoo = meu;
    try {
      const resposta = await fetch(this.url, { method: "POST", body: dados });
      if (!resposta.ok) throw new Error(String(resposta.status));
      const corpo = await resposta.json();
      if (!corpo.salvo) {
        this.ultima = "";  // tentar de novo na próxima mudança
        // `mensagem` é o texto para a pessoa (termos, OS); sem ele, o aviso do roteiro.
        this.anunciar(corpo.mensagem || "Ainda não dá para salvar — complete a origem e um destino.", false, Boolean(corpo.mensagem));
        return;
      }
      const campoId = /** @type {HTMLInputElement | null} */ (this.form.querySelector("[data-roteiro-id]"));
      if (campoId && !campoId.value) campoId.value = String(corpo.id);
      // Campos que o servidor devolve (ex.: a versão nova do ofício) voltam para o
      // formulário: sem isso o próximo salvamento brigaria com a gravação de agora.
      for (const [nome, valor] of Object.entries(corpo.campos || {})) {
        const campo = /** @type {HTMLInputElement | null} */ (
          this.form.querySelector(`[name="${nome}"]`)
        );
        if (campo) campo.value = String(valor);
      }
      if (corpo.recarregar) {
        this.enviando = true;  // nada mais a gravar: a página volta já com tudo
        this.anunciar("Salvo — atualizando a tela…", true);
        window.location.reload();
        return;
      }
      this.anunciar(`Salvo automaticamente às ${corpo.em}`, true);
      // Quem mostra o documento pode se refazer com os dados novos (editor-documento.js).
      document.documentElement.dataset.dadosSalvos = "1"; // para quem carregar depois
      document.dispatchEvent(new CustomEvent("pcpr:dados-salvos"));
      this.atualizarRegioes();
    } catch {
      this.ultima = "";
      this.anunciar("Não foi possível salvar agora — suas alterações continuam na tela.");
    } finally {
      if (this.emVoo === meu) this.emVoo = null;
      terminar();
    }
  }

  /** Troca as regiões `[data-vivo][id]` pelas da página refeita no servidor. */
  async atualizarRegioes() {
    const vivas = [...document.querySelectorAll("[data-vivo][id]")];
    if (!vivas.length) return;
    try {
      const r = await fetch(window.location.pathname + window.location.search,
        { headers: { Accept: "text/html" } });
      if (!r.ok) return;
      const nova = new DOMParser().parseFromString(await r.text(), "text/html");
      for (const atual of vivas) {
        const outra = nova.getElementById(atual.id);
        // Quem está sendo usado não muda debaixo da mão (volta na próxima gravação).
        if (!outra || atual.contains(document.activeElement)) continue;
        atual.replaceWith(document.adoptNode(outra));
      }
      // Quem tem mais a refazer com a página nova olha nela (ex.: o bloco de editores do
      // termo, quando surge um documento — editores.js).
      document.dispatchEvent(new CustomEvent("pcpr:pagina-refeita", { detail: { pagina: nova } }));
    } catch { /* informativo: a tela continua válida, só menos atual */ }
  }

  /** @param {string} texto @param {boolean} ok @param {boolean} erro */
  anunciar(texto, ok = false, erro = false) {
    if (!this.status) return;
    const alvo = /** @type {HTMLElement} */ (this.status.querySelector("[data-anuncio]") || this.status);
    alvo.textContent = texto;
    this.status.classList.toggle("barra-acoes__status--salvo", ok);
    this.status.classList.toggle("barra-acoes__status--erro", erro);
    this.status.classList.remove("barra-acoes__status--sujo");
  }
}

document.querySelectorAll("form[data-autosave]").forEach((f) => {
  new Autosave(/** @type {HTMLFormElement} */ (f));
});

document.addEventListener("submit", (e) => {
  const form = /** @type {HTMLFormElement} */ (e.target);
  if (!form.matches("[data-esperar-salvamento]") || form.dataset.descarregado) return;
  if (!Autosave.todos.length) return;
  e.preventDefault();
  const quem = /** @type {HTMLElement | null} */ (e.submitter);
  Promise.all(Autosave.todos.map((a) => a.descarregar())).finally(() => {
    form.dataset.descarregado = "1";
    form.requestSubmit(quem ?? undefined);
  });
});
