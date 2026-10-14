// @ts-check
/**
 * <pc-hora> — campo hh:mm com relógio próprio, sem rolagem: as 24 horas numa grade de
 * quatro faixas do dia (madrugada, manhã, tarde, noite) e os minutos de 5 em 5 numa grade
 * de duas linhas. No topo, o horário que está sendo montado. Cada grade é uma lista
 * (listbox) navegável por teclado: ←/→ andam uma casa, ↑/↓ uma linha, Tab troca de grade,
 * Enter confirma (na hora, segue para os minutos; nos minutos, fecha) e Esc fecha.
 * Minutos fora do passo continuam sendo digitados.
 */
import { SeletorFlutuante } from "./seletor-base.js";

/** @param {number} n */
const dois = (n) => String(n).padStart(2, "0");

const COLUNAS = 6;
const FAIXAS = ["Madrugada", "Manhã", "Tarde", "Noite"];

export class PcHora extends SeletorFlutuante {
  classePainel = "relogio";
  textoBotao = "Escolher hora";
  /** @type {HTMLUListElement[]} */
  colunas = [];
  /** @type {HTMLElement[]} */
  visor = [];

  montar() {
    const painel = /** @type {HTMLElement} */ (this.painel);
    if (this.colunas.length > 0) return;

    const topo = document.createElement("p");
    topo.className = "relogio__visor";
    topo.setAttribute("aria-hidden", "true");
    const [hh, sep, mm] = ["span", "span", "span"].map((t) => document.createElement(t));
    sep.className = "relogio__separador";
    sep.textContent = ":";
    this.visor = [hh, mm];
    hh.className = mm.className = "relogio__parte";
    topo.append(hh, sep, mm);
    painel.append(topo);

    [["Hora", 24, 1], ["Minutos", 12, 5]].forEach(([titulo, quantos, passo], indice) => {
      const grupo = document.createElement("div");
      grupo.className = `relogio__grupo relogio__grupo--${indice === 0 ? "horas" : "minutos"}`;
      const rotulo = document.createElement("p");
      rotulo.className = "relogio__titulo";
      rotulo.id = `${painel.id}-t${indice}`;
      rotulo.textContent = String(titulo);
      const corpo = document.createElement("div");
      corpo.className = "relogio__corpo";
      if (indice === 0) {
        const faixas = document.createElement("div");
        faixas.className = "relogio__faixas";
        faixas.setAttribute("aria-hidden", "true");
        FAIXAS.forEach((nome) => {
          const f = document.createElement("span");
          f.textContent = nome;
          faixas.append(f);
        });
        corpo.append(faixas);
      }
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
      lista.addEventListener("focus", () => this.destacar(indice));
      lista.addEventListener("click", (e) => {
        const li = /** @type {HTMLElement} */ (e.target).closest("li");
        if (!li) return;
        this.definir(indice, /** @type {HTMLElement} */ (li));
        if (indice === 0) this.colunas[1].focus();
        else this.fechar(true);
      });
      corpo.append(lista);
      grupo.append(rotulo, corpo);
      painel.append(grupo);
      this.colunas.push(lista);
    });
  }

  /** Acende no visor a parte que está sendo escolhida. @param {number} indice */
  destacar(indice) {
    this.visor.forEach((p, i) => p.classList.toggle("relogio__parte--ativa", i === indice));
  }

  /** Lê "hh:mm" do campo e marca as opções correspondentes. */
  marcar() {
    const m = /^(\d{1,2}):(\d{2})$/.exec(/** @type {HTMLInputElement} */ (this.entrada).value.trim());
    const partes = m ? [dois(Number(m[1])), m[2]] : ["", ""];
    this.visor.forEach((p, i) => { p.textContent = partes[i] || "--"; });
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
    this.marcar();
    this.colunas[0]?.focus();
  }

  /** @param {KeyboardEvent} e @param {number} coluna */
  teclado(e, coluna) {
    const lista = this.colunas[coluna];
    const opcoes = /** @type {HTMLElement[]} */ (Array.from(lista.children));
    const atual = opcoes.findIndex((li) => li.classList.contains("relogio__ativo"));
    const ultimo = opcoes.length - 1;
    /** @type {Record<string, number>} */
    const destino = {
      ArrowRight: Math.min(ultimo, atual + 1),
      ArrowLeft: Math.max(0, atual - 1),
      ArrowDown: atual + COLUNAS <= ultimo ? atual + COLUNAS : atual,
      ArrowUp: atual - COLUNAS >= 0 ? atual - COLUNAS : atual,
      Home: 0,
      End: ultimo,
    };
    if (e.key in destino) {
      e.preventDefault();
      this.definir(coluna, opcoes[destino[e.key]]);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (atual >= 0) this.definir(coluna, opcoes[atual]);
      if (coluna === 0) this.colunas[1].focus();
      else this.fechar(true);
    }
  }
}

customElements.define("pc-hora", PcHora);
