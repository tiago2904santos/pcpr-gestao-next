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
 */

/** @typedef {{id: string, unidade: string, nome: string, motorista: boolean}} Membro */

export class PcTransporte extends HTMLElement {
  connectedCallback() {
    this.select = /** @type {HTMLSelectElement | null} */ (this.querySelector("select[name='viatura']"));
    this.tipo = /** @type {HTMLSelectElement | null} */ (this.querySelector("select[name='tipo_transporte']"));
    if (!this.select) return;
    this.ordemOriginal = Array.from(this.select.options);
    this.motoristaAnterior = this.equipe().find((m) => m.motorista)?.id || "";
    this.sugerir();
    // O HTMX troca o bloco #equipe inteiro (outerHTML): o `HX-Trigger` cai num elemento já
    // fora da página e não chega ao body. O que chega é o fim da troca, com a rota pedida.
    this.aoMudarEquipe = (/** @type {Event} */ e) => {
      const rota = /** @type {CustomEvent} */ (e).detail?.pathInfo?.requestPath || "";
      if (!/\/equipe\//.test(rota)) return;
      this.sugerir();
      this.escolherPeloMotorista();
    };
    document.body.addEventListener("htmx:afterSettle", this.aoMudarEquipe);
  }

  disconnectedCallback() {
    if (this.aoMudarEquipe) document.body.removeEventListener("htmx:afterSettle", this.aoMudarEquipe);
  }

  /** @returns {Membro[]} */
  equipe() {
    return Array.from(document.querySelectorAll("#equipe [data-servidor]")).map((el) => {
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
    const primeiro = motorista.nome.split(" ")[0];
    document.body.dispatchEvent(new CustomEvent("toast", {
      detail: { mensagem: `Viatura ${opcao.textContent?.trim()} escolhida: ${primeiro} costuma dirigi-la. Salve o rascunho para confirmar.`, nivel: "info" },
    }));
  }
}

customElements.define("pc-transporte", PcTransporte);
