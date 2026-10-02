// @ts-check
/**
 * <pc-hora> — campo hh:mm com relógio próprio: duas colunas (horas e minutos de 5 em 5),
 * cada uma uma lista (listbox) navegável por teclado. ↑/↓ mudam o valor na hora, ←/→
 * trocam de coluna, Enter confirma e Esc fecha. Minutos fora do passo são digitados.
 */
import { SeletorFlutuante } from "./seletor-base.js";

/** @param {number} n */
const dois = (n) => String(n).padStart(2, "0");

export class PcHora extends SeletorFlutuante {
  classePainel = "relogio";
  textoBotao = "Escolher hora";
  /** @type {HTMLUListElement[]} */
  colunas = [];

  montar() {
    const painel = /** @type {HTMLElement} */ (this.painel);
    if (this.colunas.length === 0) {
      [["Horas", 24, 1], ["Minutos", 12, 5]].forEach(([titulo, quantos, passo], indice) => {
        const coluna = document.createElement("div");
        coluna.className = "relogio__coluna";
        const rotulo = document.createElement("p");
        rotulo.className = "relogio__titulo";
        rotulo.id = `${painel.id}-t${indice}`;
        rotulo.textContent = String(titulo);
        const lista = document.createElement("ul");
        lista.className = "relogio__lista";
        lista.id = `${painel.id}-l${indice}`;
        lista.tabIndex = 0;
        lista.setAttribute("role", "listbox");
        lista.setAttribute("aria-labelledby", rotulo.id);
        for (let i = 0; i < Number(quantos); i += 1) {
          const li = document.createElement("li");
          li.id = `${lista.id}-${i}`;
          li.setAttribute("role", "option");
          li.dataset.valor = dois(i * Number(passo));
          li.textContent = li.dataset.valor;
          lista.append(li);
        }
        lista.addEventListener("keydown", (e) => this.teclado(e, indice));
        lista.addEventListener("click", (e) => {
          const li = /** @type {HTMLElement} */ (e.target).closest("li");
          if (!li) return;
          this.definir(indice, /** @type {HTMLElement} */ (li));
          if (indice === 0) this.colunas[1].focus();
          else this.fechar(true);
        });
        coluna.append(rotulo, lista);
        painel.append(coluna);
        this.colunas.push(lista);
      });
    }
  }

  /** Lê "hh:mm" do campo e marca as opções correspondentes. */
  marcar() {
    const m = /^(\d{1,2}):(\d{2})$/.exec(/** @type {HTMLInputElement} */ (this.entrada).value.trim());
    const partes = m ? [dois(Number(m[1])), m[2]] : ["", ""];
    this.colunas.forEach((lista, i) => {
      const opcoes = Array.from(lista.children);
      opcoes.forEach((li) => li.setAttribute("aria-selected", String(/** @type {HTMLElement} */ (li).dataset.valor === partes[i])));
      // Minuto fora do passo (ex.: 07): destaca o mais próximo, sem marcar como escolhido.
      const alvo = opcoes.find((li) => li.getAttribute("aria-selected") === "true")
        || (i === 1 && m ? opcoes[Math.min(11, Math.round(Number(m[2]) / 5))] : opcoes[i === 0 ? 8 : 0]);
      this.ativar(lista, /** @type {HTMLElement} */ (alvo));
    });
  }

  /** @param {HTMLUListElement} lista @param {HTMLElement} li */
  ativar(lista, li) {
    lista.setAttribute("aria-activedescendant", li.id);
    lista.querySelectorAll(".relogio__ativo").forEach((o) => o.classList.remove("relogio__ativo"));
    li.classList.add("relogio__ativo");
    lista.scrollTop = li.offsetTop - lista.clientHeight / 2 + li.clientHeight / 2;
  }

  /** @param {number} coluna @param {HTMLElement} li */
  definir(coluna, li) {
    const atual = /^(\d{1,2}):(\d{2})$/.exec(/** @type {HTMLInputElement} */ (this.entrada).value.trim());
    const partes = atual ? [dois(Number(atual[1])), atual[2]] : ["08", "00"];
    partes[coluna] = li.dataset.valor || "00";
    this.escrever(`${partes[0]}:${partes[1]}`);
    this.marcar();
  }

  focarInicial() {
    this.marcar(); // já visível: a rolagem até a hora atual só funciona agora
    this.colunas[0]?.focus();
  }

  /** @param {KeyboardEvent} e @param {number} coluna */
  teclado(e, coluna) {
    const lista = this.colunas[coluna];
    const opcoes = /** @type {HTMLElement[]} */ (Array.from(lista.children));
    const atual = opcoes.findIndex((li) => li.classList.contains("relogio__ativo"));
    /** @type {Record<string, number>} */
    const destino = {
      ArrowDown: Math.min(opcoes.length - 1, atual + 1),
      ArrowUp: Math.max(0, atual - 1),
      Home: 0,
      End: opcoes.length - 1,
    };
    if (e.key in destino) {
      e.preventDefault();
      this.definir(coluna, opcoes[destino[e.key]]);
    } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      this.colunas[coluna === 0 ? 1 : 0].focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (atual >= 0) this.definir(coluna, opcoes[atual]);
      this.fechar(true);
    }
  }
}

customElements.define("pc-hora", PcHora);
