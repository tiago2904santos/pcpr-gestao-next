// @ts-check
/**
 * <pc-data> — campo dd/mm/aaaa com calendário próprio (padrão "Date Picker Dialog" do
 * WAI-ARIA APG). Teclado na grade: setas (dia/semana), Home/End (início/fim da semana),
 * PageUp/PageDown (mês; com Shift, ano), Enter/Espaço escolhem, Esc fecha.
 *
 * Intervalo: com `data-ate="<id de outro campo de data>"`, o mesmo calendário marca começo e
 * fim — o primeiro clique abre o período, o segundo fecha, e os dias entre eles aparecem
 * marcados. Sem JavaScript continuam dois campos de data comuns.
 *
 * Período num campo só: com `data-periodo`, o campo visível mostra "13/10/2026 a 20/10/2026"
 * (e aceita ser digitado assim) enquanto dois campos escondidos — `[data-periodo-de]` e
 * `[data-periodo-ate]` — levam as datas ao formulário. Serve a filtros, onde duas caixas
 * para uma ideia só ("o período") pesam mais do que ajudam.
 */
import { SeletorFlutuante } from "./seletor-base.js";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
  "setembro", "outubro", "novembro", "dezembro"];
const SEMANA = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
  "sexta-feira", "sábado"];

/** @param {number} n */
const dois = (n) => String(n).padStart(2, "0");
/** @param {Date} d */
const formatar = (d) => `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()}`;
/** @param {Date} a @param {Date} b */
const mesmoDia = (a, b) => a.toDateString() === b.toDateString();

/** Separador do período escrito no campo: "13/10/2026 a 20/10/2026" (ou com travessão). */
const SEPARADOR = /\s+(?:a|–|—|-)\s+|\s*[–—]\s*/;

/** "8/10/2026" → Date (ou null se não for uma data real). @param {string} texto */
function lerData(texto) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(texto.trim());
  if (!m) return null;
  const [dia, mes, ano] = [Number(m[1]), Number(m[2]) - 1, Number(m[3])];
  const d = new Date(ano, mes, dia);
  return d.getDate() === dia && d.getMonth() === mes ? d : null;
}

/** Soma meses mantendo o dia (31/01 + 1 mês → 28 ou 29/02). @param {Date} d @param {number} n */
function somarMeses(d, n) {
  const alvo = new Date(d.getFullYear(), d.getMonth() + n, 1);
  const ultimo = new Date(alvo.getFullYear(), alvo.getMonth() + 1, 0).getDate();
  alvo.setDate(Math.min(d.getDate(), ultimo));
  return alvo;
}

export class PcData extends SeletorFlutuante {
  classePainel = "calendario";
  textoBotao = "Escolher data";
  foco = new Date();
  /** Já há um começo escolhido e o próximo clique fecha o período. */
  aguardandoFim = false;

  /** Campo do fim do período, quando este calendário marca um intervalo. */
  get campoFim() {
    const id = this.dataset.ate;
    return id ? /** @type {HTMLInputElement | null} */ (document.getElementById(id)) : null;
  }

  /** Um campo só para o período inteiro (filtros). */
  get ehPeriodo() {
    return this.hasAttribute("data-periodo");
  }

  /** Este calendário marca duas pontas? */
  get temFim() {
    return this.ehPeriodo || Boolean(this.campoFim);
  }

  get inicioAtual() {
    const texto = /** @type {HTMLInputElement} */ (this.entrada).value;
    return lerData(this.ehPeriodo ? texto.split(SEPARADOR)[0] || "" : texto);
  }

  get fimAtual() {
    if (this.ehPeriodo) {
      const texto = /** @type {HTMLInputElement} */ (this.entrada).value;
      return lerData(texto.split(SEPARADOR)[1] || "");
    }
    return this.campoFim ? lerData(this.campoFim.value) : null;
  }

  connectedCallback() {
    super.connectedCallback();
    // Digitar o período à mão também vale: os campos escondidos acompanham o que foi escrito.
    if (this.ehPeriodo && this.entrada) {
      this.entrada.addEventListener("change", () => this.gravarEscondidos(this.inicioAtual,
                                                                          this.fimAtual));
    }
  }

  /** @param {Date | null} de @param {Date | null} ate */
  gravarEscondidos(de, ate) {
    for (const [seletor, valor] of [["[data-periodo-de]", de], ["[data-periodo-ate]", ate]]) {
      const campo = /** @type {HTMLInputElement | null} */ (
        this.querySelector(/** @type {string} */ (seletor)));
      if (!campo) continue;
      const texto = valor ? formatar(/** @type {Date} */ (valor)) : "";
      if (campo.value === texto) continue;
      campo.value = texto;
      campo.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  /** Grava o par escolhido onde ele mora neste modo. @param {Date | null} de @param {Date | null} ate */
  definir(de, ate) {
    if (this.ehPeriodo) {
      const texto = !de ? "" : (ate ? `${formatar(de)} a ${formatar(ate)}` : formatar(de));
      this.escrever(texto);
      this.gravarEscondidos(de, ate);
      return;
    }
    this.escrever(de ? formatar(de) : "");
    const fim = this.campoFim;
    if (!fim) return;
    fim.value = ate ? formatar(ate) : "";
    fim.dispatchEvent(new Event("change", { bubbles: true }));
  }

  montar() {
    const painel = /** @type {HTMLElement} */ (this.painel);
    const entrada = /** @type {HTMLInputElement} */ (this.entrada);
    this.foco = this.inicioAtual || new Date();
    if (!this.grade) {
      const topo = document.createElement("div");
      topo.className = "calendario__topo";
      const anterior = this.botaoDoPainel("", "calendario__nav", () => this.mudarMes(-1));
      anterior.setAttribute("aria-label", "Mês anterior");
      anterior.append(this.icone("chevron-left"));
      const proximo = this.botaoDoPainel("", "calendario__nav", () => this.mudarMes(1));
      proximo.setAttribute("aria-label", "Próximo mês");
      proximo.append(this.icone("chevron-right"));
      this.titulo = document.createElement("p");
      this.titulo.className = "calendario__mes";
      this.titulo.id = `${painel.id}-mes`;
      this.titulo.setAttribute("aria-live", "polite");
      topo.append(anterior, this.titulo, proximo);

      const grade = document.createElement("table");
      grade.className = "calendario__grade";
      grade.setAttribute("role", "grid");
      grade.setAttribute("aria-labelledby", this.titulo.id);
      const cabeca = grade.createTHead().insertRow();
      SEMANA.forEach((nome) => {
        const th = document.createElement("th");
        th.scope = "col";
        th.abbr = nome;
        th.textContent = nome[0].toUpperCase();
        cabeca.append(th);
      });
      this.corpo = grade.createTBody();
      this.corpo.addEventListener("keydown", (e) => this.teclado(e));
      this.corpo.addEventListener("click", (e) => {
        const td = /** @type {HTMLElement} */ (e.target).closest("td");
        if (td?.dataset.data) this.escolher(new Date(`${td.dataset.data}T12:00`));
      });
      this.grade = grade;

      const rodape = document.createElement("div");
      rodape.className = "calendario__rodape";
      rodape.append(
        this.botaoDoPainel("Hoje", "botao botao--sm botao--texto", () => this.escolher(new Date())),
        this.botaoDoPainel("Limpar", "botao botao--sm botao--texto", () => {
          this.definir(null, null);
          this.aguardandoFim = false;
          this.fechar(true);
        }),
      );
      painel.append(topo, grade, rodape);
    }
    this.renderizar();
  }

  renderizar() {
    const corpo = /** @type {HTMLTableSectionElement} */ (this.corpo);
    const escolhida = this.inicioAtual;
    const fim = this.fimAtual;
    const hoje = new Date();
    const [ano, mes] = [this.foco.getFullYear(), this.foco.getMonth()];
    const nomeMes = MESES[mes];
    /** @type {HTMLElement} */ (this.titulo).textContent = `${nomeMes[0].toUpperCase()}${nomeMes.slice(1)} de ${ano}`;
    const inicio = new Date(ano, mes, 1);
    inicio.setDate(1 - inicio.getDay());
    corpo.replaceChildren();
    for (let semana = 0; semana < 6; semana += 1) {
      const linha = corpo.insertRow();
      for (let dia = 0; dia < 7; dia += 1) {
        const d = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate() + semana * 7 + dia);
        const td = linha.insertCell();
        td.textContent = String(d.getDate());
        td.dataset.data = `${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}`;
        td.setAttribute("aria-label", `${d.getDate()} de ${MESES[d.getMonth()]} de ${d.getFullYear()}, ${SEMANA[d.getDay()]}`);
        td.tabIndex = mesmoDia(d, this.foco) ? 0 : -1;
        if (d.getMonth() !== mes) td.className = "calendario__fora";
        if (mesmoDia(d, hoje)) td.setAttribute("aria-current", "date");
        const extremo = Boolean((escolhida && mesmoDia(d, escolhida)) || (fim && mesmoDia(d, fim)));
        td.setAttribute("aria-selected", String(extremo));
        if (escolhida && fim && d > escolhida && d < fim) td.classList.add("calendario__intervalo");
      }
    }
  }

  focarInicial() {
    /** @type {HTMLElement | null | undefined} */ (this.corpo?.querySelector("td[tabindex='0']"))?.focus();
  }

  /** @param {Date} nova */
  irPara(nova) {
    const mudouMes = nova.getMonth() !== this.foco.getMonth() || nova.getFullYear() !== this.foco.getFullYear();
    this.foco = nova;
    if (mudouMes) this.renderizar();
    else {
      this.corpo?.querySelectorAll("td").forEach((td) => {
        td.tabIndex = td.dataset.data === `${nova.getFullYear()}-${dois(nova.getMonth() + 1)}-${dois(nova.getDate())}` ? 0 : -1;
      });
    }
    this.focarInicial();
  }

  /** @param {number} n */
  mudarMes(n) {
    this.foco = somarMeses(this.foco, n);
    this.renderizar();
  }

  /** @param {KeyboardEvent} e */
  teclado(e) {
    const d = this.foco;
    /** @param {number} n */
    const dias = (n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
    /** @type {Record<string, () => Date>} */
    const acoes = {
      ArrowLeft: () => dias(-1),
      ArrowRight: () => dias(1),
      ArrowUp: () => dias(-7),
      ArrowDown: () => dias(7),
      Home: () => dias(-d.getDay()),
      End: () => dias(6 - d.getDay()),
      PageUp: () => somarMeses(d, e.shiftKey ? -12 : -1),
      PageDown: () => somarMeses(d, e.shiftKey ? 12 : 1),
    };
    if (acoes[e.key]) {
      e.preventDefault();
      this.irPara(acoes[e.key]());
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      this.escolher(d);
    }
  }

  /** @param {Date} d */
  escolher(d) {
    if (!this.temFim) {
      this.definir(d, null);
      this.fechar(true);
      return;
    }
    if (!this.aguardandoFim) {
      // Primeiro clique: abre um período novo e espera o segundo, sem fechar o calendário.
      this.definir(d, null);
      this.aguardandoFim = true;
      this.renderizar();
      return;
    }
    // Segundo clique fecha o período; clicar antes do começo inverte os dois.
    const inicio = this.inicioAtual || d;
    const [a, b] = d < inicio ? [d, inicio] : [inicio, d];
    this.definir(a, b);
    this.aguardandoFim = false;
    this.fechar(true);
  }
}

customElements.define("pc-data", PcData);
