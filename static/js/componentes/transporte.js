// @ts-check
/**
 * <pc-transporte> — a viatura acompanha a equipe.
 *
 * Lê a equipe do bloco #equipe (cada pessoa traz data-servidor, data-unidade e
 * data-motorista) e, nas opções do <select name="viatura"> (data-unidade, data-sigla,
 * data-motoristas, data-nomes, postos pelo widget SelecaoDeViatura):
 *   - sugere primeiro as viaturas da unidade de alguém da equipe (chip "Unidade SIGLA") e as
 *     que alguém da equipe costuma dirigir (chip com o primeiro nome);
 *   - ao marcar um motorista, escolhe sozinha a viatura que ele dirige (e o meio de
 *     transporte vira "Viatura oficial"), avisando pelo toast.
 * A equipe é salva na hora (HTMX, evento `equipe-alterada`); a viatura segue no formulário
 * principal — a escolha automática só marca o campo, quem salva é a pessoa.
 *
 * É a escolha de viatura de todas as telas (viagens/_campo_viatura.html): fora do ofício a
 * equipe é o campo CampoEquipe, cujos cartões trazem os mesmos data-*; `data-equipe` diz
 * onde ela está (padrão #equipe) e o aviso de mudança é `pc-equipe-alterada`.
 */

/** @typedef {{id: string, unidade: string, nome: string, motorista: boolean}} Membro */

export class PcTransporte extends HTMLElement {
  connectedCallback() {
    this.select = /** @type {HTMLSelectElement | null} */ (
      this.querySelector("select[name='viatura']") || this.querySelector("select"));
    this.tipo = /** @type {HTMLSelectElement | null} */ (this.querySelector("select[name='tipo_transporte']"));
    if (!this.select) return;
    this.ordemOriginal = Array.from(this.select.options);
    this.motoristaAnterior = this.equipe().find((m) => m.motorista)?.id || "";
    this.sugerir();
    this.ligarMotoristaDeFora();
    this.ligarCartao();
    this.sincronizarMotoristaDeFora();
    // O HTMX troca o bloco #equipe inteiro (outerHTML): o `HX-Trigger` cai num elemento já
    // fora da página e não chega ao body. O que chega é o fim da troca, com a rota pedida.
    this.aoMudarEquipe = (/** @type {Event} */ e) => {
      const rota = /** @type {CustomEvent} */ (e).detail?.pathInfo?.requestPath || "";
      if (!/\/equipe\//.test(rota)) return;
      this.sugerir();
      this.sincronizarMotoristaDeFora();
      this.escolherPeloMotorista();
    };
    document.body.addEventListener("htmx:afterSettle", this.aoMudarEquipe);
    this.aoMudarCampoEquipe = (/** @type {Event} */ e) => {
      const area = this.areaDaEquipe();
      if (area && !area.contains(/** @type {Node} */ (e.target))) return;
      this.sugerir();
      this.sincronizarMotoristaDeFora();
      this.escolherPeloMotorista();
    };
    document.addEventListener("pc-equipe-alterada", this.aoMudarCampoEquipe);
  }

  /** Onde está a equipe desta viatura (o lote tem uma por ofício). */
  areaDaEquipe() {
    return document.querySelector(this.dataset.equipe || "#equipe");
  }

  disconnectedCallback() {
    if (this.aoMudarEquipe) document.body.removeEventListener("htmx:afterSettle", this.aoMudarEquipe);
    if (this.aoMudarCampoEquipe) document.removeEventListener("pc-equipe-alterada", this.aoMudarCampoEquipe);
    if (this.aoMudarViatura) this.select?.removeEventListener("change", this.aoMudarViatura);
    if (this.aoRemoverViatura) this.querySelector("[data-remover-viatura]")?.removeEventListener("click", this.aoRemoverViatura);
  }

  /** Variante da busca: seleção persistente em cartão, busca livre para substituir. */
  ligarCartao() {
    this.cartao = /** @type {HTMLElement | null} */ (this.querySelector("[data-viatura-cartao]"));
    if (!this.cartao || !this.select) return;
    this.aoMudarViatura = () => this.sincronizarCartao();
    this.select.addEventListener("change", this.aoMudarViatura);
    this.aoRemoverViatura = () => {
      if (!this.select) return;
      this.select.value = "";
      this.select.dispatchEvent(new Event("change", { bubbles: true }));
      /** @type {HTMLInputElement | null} */ (this.querySelector("pc-combobox[data-escolha-em-cartao] input[role='combobox']"))?.focus();
    };
    this.querySelector("[data-remover-viatura]")?.addEventListener("click", this.aoRemoverViatura);
    this.cartao.addEventListener("animationend", () => this.cartao?.removeAttribute("data-escolhida-pelo-motorista"));
    this.sincronizarCartao();
  }

  sincronizarCartao() {
    const cartao = this.cartao;
    const opcao = this.select?.selectedOptions[0];
    if (!cartao) return;
    cartao.hidden = !opcao?.value;
    cartao.removeAttribute("data-escolhida-pelo-motorista");
    const origem = /** @type {HTMLElement | null} */ (cartao.querySelector("[data-recurso-origem]"));
    if (origem) origem.hidden = true;
    if (!opcao?.value) return;
    for (const [seletor, texto] of [
      ["[data-recurso-titulo]", opcao.textContent?.trim() || "Viatura"],
      ["[data-recurso-meta]", opcao.dataset.meta || "Cadastro sem detalhes adicionais"],
    ]) {
      const campo = cartao.querySelector(seletor);
      if (campo instanceof HTMLElement) { campo.textContent = texto; campo.title = texto; }
    }
    cartao.querySelector("[data-remover-viatura]")?.setAttribute("aria-label", `Remover viatura ${opcao.textContent?.trim()}`);
  }

  /** A marcação da equipe já substituiu o externo no servidor. Não reenviar o modo antigo. */
  sincronizarMotoristaDeFora() {
    const bloco = /** @type {HTMLDetailsElement | null} */ (this.querySelector("details.motorista-externo"));
    if (!bloco) return;
    bloco.hidden = this.equipe().some((m) => m.motorista);
    if (!bloco.hidden) return;
    bloco.open = false;
    const quem = /** @type {HTMLSelectElement | null} */ (bloco.querySelector("select[name='motorista_externo']"));
    if (quem) quem.value = "";
    for (const campo of bloco.querySelectorAll("input, select, textarea")) {
      /** @type {HTMLInputElement} */ (campo).disabled = true;
    }
  }

  /** @returns {Membro[]} */
  equipe() {
    const area = this.areaDaEquipe();
    return Array.from(area ? area.querySelectorAll("[data-servidor]") : []).map((el) => {
      const e = /** @type {HTMLElement} */ (el);
      return {
        id: e.dataset.servidor || "",
        unidade: e.dataset.unidade || "",
        nome: e.dataset.nome || "",
        motorista: e.hasAttribute("data-motorista"),
      };
    });
  }

  /** Reordena as opções (sugeridas primeiro) e põe os chips de cada uma. */
  sugerir() {
    const select = this.select;
    if (!select || !this.ordemOriginal) return;
    const equipe = this.equipe();
    const unidades = new Map(equipe.map((m) => [m.unidade, true]));
    const porId = new Map(equipe.map((m) => [m.id, m]));
    /** @type {HTMLOptionElement[]} */
    const sugeridas = [];
    /** @type {HTMLOptionElement[]} */
    const outras = [];
    for (const o of this.ordemOriginal) {
      if (!o.value) continue;
      /** @type {string[]} */
      const chips = [];
      const ids = (o.dataset.motoristas || "").split(" ").filter(Boolean);
      const nomes = (o.dataset.nomes || "").split("|");
      ids.forEach((id, i) => {
        const membro = porId.get(id);
        if (membro) chips.push(membro.nome.split(" ")[0] || nomes[i] || "Motorista");
      });
      if (o.dataset.unidade && unidades.has(o.dataset.unidade)) chips.push(`Unidade ${o.dataset.sigla || ""}`.trim());
      if (chips.length) {
        o.dataset.chips = chips.join("|");
        o.dataset.grupo = "Sugeridas pela equipe";
        sugeridas.push(o);
      } else {
        delete o.dataset.chips;
        o.dataset.grupo = sugeridas.length || equipe.length ? "Outras viaturas" : "";
        outras.push(o);
      }
    }
    // O <select> guarda a ordem que a lista mostra; a opção vazia fica onde está.
    const valor = select.value;
    for (const o of [...sugeridas, ...outras]) select.append(o);
    if (!sugeridas.length) for (const o of outras) delete o.dataset.grupo;
    select.value = valor;
  }

  /** Abrir e fechar "Motorista de fora da equipe" é que liga e desliga o caso.
   *
   * A escolha "Quem dirige" não tem mais "Alguém da equipe" (isso se marca na equipe): ela
   * só diz QUEM é o de fora. Então abrir o bloco sem nada escolhido já assume a primeira
   * opção, e fechá-lo devolve o campo a vazio — é o que grava "não há motorista de fora".
   */
  ligarMotoristaDeFora() {
    const bloco = /** @type {HTMLDetailsElement | null} */ (this.querySelector("details.motorista-externo"));
    const quem = /** @type {HTMLSelectElement | null} */ (
      this.querySelector("select[name='motorista_externo']"));
    if (!bloco || !quem) return;
    const primeira = () => Array.from(quem.options).find((o) => o.value)?.value || "";
    const campos = Array.from(bloco.querySelectorAll("input, select, textarea"));
    const habilitar = () => {
      for (const campo of campos) {
        /** @type {HTMLInputElement} */ (campo).disabled = !bloco.open;
      }
    };
    habilitar();
    const atualizarPessoa = () => {
      const titulo = bloco.querySelector(".pessoa-externa__titulo");
      const descricao = bloco.querySelector(".pessoa-externa__descricao");
      const manual = /** @type {HTMLInputElement | null} */ (bloco.querySelector("input[name='motorista_externo_nome']"));
      const servidor = /** @type {HTMLInputElement | null} */ (bloco.querySelector("input[name='motorista_externo_servidor']"));
      const busca = /** @type {HTMLInputElement | null} */ (bloco.querySelector("#busca-motorista-externo"));
      const nome = quem.value === "manual" ? manual?.value.trim() : servidor?.value ? busca?.value.trim() : "";
      if (titulo) titulo.textContent = nome || "Motorista de outro ofício";
      const origem = /** @type {HTMLInputElement | null} */ (bloco.querySelector("input[name='motorista_oficio_origem']"));
      const protocolo = /** @type {HTMLInputElement | null} */ (bloco.querySelector("input[name='motorista_protocolo_origem']"));
      if (descricao) descricao.textContent = nome
        ? ["Motorista de outro ofício", origem?.value.trim(), protocolo?.value.trim()].filter(Boolean).join(" · ")
        : "Viaja por outro ofício; não entra nas diárias desta equipe.";
    };
    for (const evento of ["input", "change", "pc-selecionado"]) bloco.addEventListener(evento, atualizarPessoa);
    atualizarPessoa();
    bloco.addEventListener("toggle", () => {
      habilitar();
      const novo = bloco.open ? (quem.value || primeira()) : "";
      if (quem.value === novo) return;
      quem.value = novo;
      atualizarPessoa();
      quem.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  /** Marcou um motorista: a viatura que ele dirige entra sozinha. */
  escolherPeloMotorista() {
    const select = this.select;
    if (!select) return;
    const motorista = this.equipe().find((m) => m.motorista);
    const anterior = this.motoristaAnterior;
    this.motoristaAnterior = motorista ? motorista.id : "";
    if (!motorista || motorista.id === anterior) return;
    const opcao = Array.from(select.options).find((o) =>
      (o.dataset.motoristas || "").split(" ").includes(motorista.id));
    if (!opcao || select.value === opcao.value) return;
    select.value = opcao.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    if (this.tipo && this.tipo.value !== "viatura") {
      this.tipo.value = "viatura";
      this.tipo.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (this.cartao) {
      this.cartao.setAttribute("data-escolhida-pelo-motorista", "");
      const origem = /** @type {HTMLElement | null} */ (this.cartao.querySelector("[data-recurso-origem]"));
      if (origem) origem.hidden = false;
    }
    const primeiro = motorista.nome.split(" ")[0];
    document.body.dispatchEvent(new CustomEvent("toast", {
      detail: { mensagem: `Viatura ${opcao.textContent?.trim()} escolhida: ${primeiro} costuma dirigi-la. Salve o rascunho para confirmar.`, nivel: "info" },
    }));
  }
}

customElements.define("pc-transporte", PcTransporte);
