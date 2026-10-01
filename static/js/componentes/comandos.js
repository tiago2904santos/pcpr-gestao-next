// @ts-check
/**
 * <pc-comandos> — paleta de comandos / busca global (Ctrl+K ou "/").
 * Combina atalhos de navegação (lidos do menu lateral, respeitando permissões)
 * com resultados do servidor (`data-fonte`), ex.: "131/2026" abre o ofício.
 */

/** @typedef {{titulo: string, meta?: string, url: string, grupo: string, icone?: string}} Item */

/** @param {string} t */
const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export class PcComandos extends HTMLElement {
  /** @type {Item[]} */
  itens = [];
  ativo = 0;

  connectedCallback() {
    this.dialogo = /** @type {HTMLDialogElement} */ (this.querySelector("dialog"));
    this.entrada = /** @type {HTMLInputElement} */ (this.querySelector("input"));
    this.lista = /** @type {HTMLUListElement} */ (this.querySelector("[role='listbox']"));
    this.sprite = this.dataset.sprite || "";
    /** @type {number | undefined} */
    this.atraso = undefined;

    document.querySelectorAll("[data-abrir-comandos]").forEach((b) =>
      b.addEventListener("click", () => this.abrir()),
    );
    document.addEventListener("keydown", (e) => {
      const alvo = /** @type {HTMLElement} */ (e.target);
      const digitando = alvo.closest("input, textarea, select, [contenteditable='true']");
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.abrir();
      } else if (e.key === "/" && !digitando && !this.dialogo?.open) {
        e.preventDefault();
        this.abrir();
      }
    });
    this.entrada?.addEventListener("input", () => {
      window.clearTimeout(this.atraso);
      this.atraso = window.setTimeout(() => this.atualizar(), 150);
    });
    this.entrada?.addEventListener("keydown", (e) => this.teclado(e));
    this.lista?.addEventListener("click", (e) => {
      const li = /** @type {HTMLElement} */ (e.target).closest("[role='option']");
      if (li) this.ir(Number(/** @type {HTMLElement} */ (li).dataset.indice));
    });
  }

  navegacao() {
    /** @type {Item[]} */
    const itens = [];
    document.querySelectorAll("#navegacao-principal a[href]").forEach((a) => {
      const rotulo = a.textContent?.trim() || "";
      itens.push({ titulo: rotulo, url: a.getAttribute("href") || "#", grupo: "Ir para", icone: "arrow-right" });
    });
    return itens;
  }

  abrir() {
    if (!this.dialogo || !this.entrada) return;
    this.entrada.value = "";
    this.dialogo.showModal();
    this.atualizar();
  }

  async atualizar() {
    const termo = this.entrada?.value.trim() || "";
    const n = normalizar(termo);
    let itens = this.navegacao().filter((i) => !n || normalizar(i.titulo).includes(n));
    if (termo.length >= 2 && this.dataset.fonte) {
      try {
        const r = await fetch(`${this.dataset.fonte}${encodeURIComponent(termo)}`, {
          headers: { Accept: "application/json" },
        });
        const dados = await r.json();
        itens = [...(dados.resultados || []), ...itens];
      } catch {
        /* a busca no servidor é um extra; a navegação local continua funcionando */
      }
    }
    this.itens = itens.slice(0, 30);
    this.ativo = 0;
    this.renderizar();
  }

  renderizar() {
    if (!this.lista) return;
    this.lista.replaceChildren();
    if (this.itens.length === 0) {
      const vazio = document.createElement("li");
      vazio.className = "combobox__vazio";
      vazio.textContent = "Nada encontrado. Tente o número do ofício (ex.: 131/2026) ou um nome.";
      this.lista.append(vazio);
      return;
    }
    let grupoAtual = "";
    this.itens.forEach((item, i) => {
      if (item.grupo !== grupoAtual) {
        grupoAtual = item.grupo;
        const g = document.createElement("li");
        g.className = "comandos__grupo rotulo-caixa-alta";
        g.setAttribute("role", "presentation");
        g.textContent = grupoAtual;
        this.lista?.append(g);
      }
      const li = document.createElement("li");
      li.className = "comandos__opcao";
      li.id = `comando-${i}`;
      li.setAttribute("role", "option");
      li.dataset.indice = String(i);
      li.setAttribute("aria-selected", String(i === this.ativo));
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("class", "icone");
      svg.setAttribute("aria-hidden", "true");
      const use = document.createElementNS(svgNS, "use");
      use.setAttribute("href", `${this.sprite}#i-${item.icone || "file-text"}`);
      svg.append(use);
      const texto = document.createElement("div");
      const t = document.createElement("div");
      t.textContent = item.titulo;
      texto.append(t);
      if (item.meta) {
        const m = document.createElement("div");
        m.className = "combobox__opcao-meta";
        m.textContent = item.meta;
        texto.append(m);
      }
      li.append(svg, texto);
      this.lista?.append(li);
    });
    this.entrada?.setAttribute("aria-activedescendant", `comando-${this.ativo}`);
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    if (e.key === "Escape") {
      // Em input type=search o Esc só limparia o texto; aqui ele fecha a paleta.
      e.preventDefault();
      this.dialogo?.close();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const passo = e.key === "ArrowDown" ? 1 : -1;
      this.ativo = (this.ativo + passo + this.itens.length) % Math.max(this.itens.length, 1);
      this.renderizar();
      this.lista?.querySelector("[aria-selected='true']")?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      this.ir(this.ativo);
    }
  }

  /** @param {number} i */
  ir(i) {
    const item = this.itens[i];
    if (item) window.location.assign(item.url);
  }
}

customElements.define("pc-comandos", PcComandos);
