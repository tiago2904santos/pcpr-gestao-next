// @ts-check
/**
 * Base dos seletores com painel flutuante ancorado ao campo (<pc-data>, <pc-hora>).
 *
 * O campo de texto continua sendo o valor do formulário (digitável, com máscara). O botão
 * dentro do campo (renderizado pelo servidor, `hidden` até o JS chegar) abre um painel
 * não modal: Esc fecha e devolve o foco ao botão; clique ou foco fora fecham.
 */

let contador = 0;

/** Texto do rótulo do campo, sem marcadores (*, "(opcional)"…). @param {HTMLInputElement} entrada */
function nomeDoCampo(entrada) {
  const ids = (entrada.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
  const textos = ids.length
    ? ids.map((id) => document.getElementById(id)?.textContent || "")
    : [entrada.labels?.[0]?.textContent || ""];
  return textos
    .join(" ")
    .replace(/\*|\((opcional|necessário para emitir)\)/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Rola a janela até o elemento caber acima da barra de ações fixa. @param {HTMLElement} el */
export function abrirEspaco(el) {
  // A barra flutua acima da borda da janela: o limite é o topo dela, não a altura.
  const barra = document.querySelector(".barra-acoes")?.getBoundingClientRect();
  const limite = (barra && barra.height ? barra.top : window.innerHeight) - 8;
  // offsetHeight ignora a animação de entrada (scale), que encolhe o retângulo medido.
  const sobra = el.getBoundingClientRect().top + el.offsetHeight + 4 - limite;
  if (sobra > 0) window.scrollBy({ top: sobra, behavior: "instant" });
}

export class SeletorFlutuante extends HTMLElement {
  /** Classe do painel e textos — definidos pelas subclasses. */
  classePainel = "";
  textoBotao = "";

  connectedCallback() {
    if (this.dataset.pronto) return;
    const entrada = /** @type {HTMLInputElement | null} */ (this.querySelector("input"));
    const botao = /** @type {HTMLButtonElement | null} */ (this.querySelector(".seletor__botao"));
    if (!entrada || !botao) return;
    this.dataset.pronto = "1";
    contador += 1;
    this.entrada = entrada;
    this.botao = botao;
    const painel = document.createElement("div");
    painel.className = `seletor__painel ${this.classePainel}`;
    painel.id = `seletor-${contador}`;
    painel.hidden = true;
    painel.setAttribute("role", "dialog");
    this.painel = painel;
    this.append(painel);

    const nome = nomeDoCampo(entrada);
    botao.setAttribute("aria-controls", painel.id);
    botao.setAttribute("aria-label", nome ? `${this.textoBotao}: ${nome}` : this.textoBotao);
    painel.setAttribute("aria-label", nome ? `${this.textoBotao}: ${nome}` : this.textoBotao);
    botao.disabled = entrada.disabled || entrada.readOnly;
    botao.hidden = false;
    this.classList.add("seletor--ativo");

    botao.addEventListener("click", () => (this.aberto ? this.fechar(true) : this.abrir()));
    painel.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation(); // não fecha gaveta/diálogo por trás
      this.fechar(true);
    });
    this.addEventListener("focusout", (e) => {
      const destino = /** @type {Node | null} */ (e.relatedTarget);
      if (this.aberto && destino && !this.contains(destino)) this.fechar(false);
    });
    document.addEventListener("pointerdown", (e) => {
      if (this.aberto && !this.contains(/** @type {Node} */ (e.target))) this.fechar(false);
    });
  }

  get aberto() {
    return Boolean(this.painel && !this.painel.hidden);
  }

  abrir() {
    if (!this.painel || !this.botao) return;
    this.montar();
    this.painel.hidden = false;
    this.botao.setAttribute("aria-expanded", "true");
    this.posicionar();
    this.focarInicial();
  }

  /** @param {boolean} devolverFoco */
  fechar(devolverFoco) {
    if (!this.painel || !this.botao || this.painel.hidden) return;
    this.painel.hidden = true;
    this.botao.setAttribute("aria-expanded", "false");
    if (devolverFoco) this.botao.focus();
  }

  /** Abre sempre para baixo (acima ficaria sob a faixa fixa do topo) e rola a página o
   * bastante para o painel não ficar sob a barra de ações; alinha à direita quando
   * passaria da tela. */
  posicionar() {
    const painel = /** @type {HTMLElement} */ (this.painel);
    painel.classList.remove("seletor__painel--direita");
    if (this.getBoundingClientRect().left + painel.offsetWidth > document.documentElement.clientWidth - 8) {
      painel.classList.add("seletor__painel--direita");
    }
    abrirEspaco(painel);
  }

  /** Escreve no campo e avisa o formulário (proteção de alterações, HTMX). @param {string} valor */
  escrever(valor) {
    const entrada = /** @type {HTMLInputElement} */ (this.entrada);
    if (entrada.value === valor) return;
    entrada.value = valor;
    entrada.dispatchEvent(new Event("input", { bubbles: true }));
    entrada.dispatchEvent(new Event("change", { bubbles: true }));
  }

  /** Ícone do sprite (mesmo arquivo do ícone do botão). @param {string} nome */
  icone(nome) {
    const uso = this.botao?.querySelector("use")?.getAttribute("href") || "";
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icone");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `${uso.split("#")[0]}#i-${nome}`);
    svg.append(use);
    return svg;
  }

  /** @param {string} texto @param {string} classe @param {() => void} acao */
  botaoDoPainel(texto, classe, acao) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = classe;
    b.textContent = texto;
    b.addEventListener("click", acao);
    return b;
  }

  /** Subclasses: constroem/atualizam o painel e escolhem onde o foco começa. */
  montar() {}
  focarInicial() {}
}
