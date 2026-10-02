// @ts-check
/**
 * Linha-guia da folha: uma linha dourada na margem esquerda do documento que nasce no alto,
 * acompanha o canto arredondado do cartão e desce até o começo da etapa da vez. Ela diz
 * "continue daqui" — se desceu, o que ficou acima já está preenchido.
 *
 * Etapa da vez: aquela em que o foco está (clicar numa etapa de baixo leva a linha junto);
 * sem foco, a primeira etapa incompleta. Etapa completa = nenhum campo obrigatório vazio
 * dentro dela; campos de etapas aninhadas contam para a de dentro. O servidor pode adiantar
 * o veredito com a classe `secao--ok` (é o que o ofício já faz pelas pendências).
 *
 * Sem JavaScript não há linha — ela é orientação, não conteúdo.
 */

const ETAPA = ".secao, .itin__bloco--etapa";

export class Guia {
  /** @type {number} */
  quadro = 0;

  /** @param {HTMLElement} raiz */
  constructor(raiz) {
    this.raiz = raiz;
    this.linha = document.createElement("div");
    this.linha.className = "documento__guia";
    this.linha.setAttribute("aria-hidden", "true");
    this.linha.hidden = true;
    raiz.prepend(this.linha);

    for (const evento of ["input", "change", "focusin", "focusout"]) {
      raiz.addEventListener(evento, () => this.agendar());
    }
    new ResizeObserver(() => this.agendar()).observe(raiz);
    this.agendar();
  }

  agendar() {
    cancelAnimationFrame(this.quadro);
    this.quadro = requestAnimationFrame(() => this.atualizar());
  }

  /** As etapas da folha, na ordem em que se lê (a de fora antes da aninhada). */
  etapas() {
    return Array.from(this.raiz.querySelectorAll(".secao__numero"))
      .map((n) => /** @type {HTMLElement | null} */ (n.closest(ETAPA)))
      .filter((e) => e !== null);
  }

  /**
   * Completa = todo campo que a tela marca com asterisco está preenchido. O critério é o
   * que a pessoa vê, não o atributo `required` (que o formset nem sempre emite).
   * @param {HTMLElement} etapa
   */
  completa(etapa) {
    if (etapa.classList.contains("secao--ok")) return true;
    return Array.from(etapa.querySelectorAll(".campo"))
      .filter((campo) => campo.closest(ETAPA) === etapa
        && campo.querySelector(".campo__obrigatorio")
        && /** @type {HTMLElement} */ (campo).offsetParent !== null)
      .every((campo) => {
        const controles = /** @type {HTMLInputElement[]} */ (
          Array.from(campo.querySelectorAll("input[name], select[name], textarea[name]")));
        return controles.filter((c) => !c.disabled)
          .every((c) => (c.value || "").trim() !== "");
      });
  }

  /** A etapa onde a pessoa deve continuar: a do foco ou a primeira incompleta. */
  alvo() {
    const etapas = this.etapas();
    const foco = document.activeElement;
    // A mais interna entre as que contêm o foco (as aninhadas vêm depois na ordem).
    const comFoco = foco instanceof Node ? etapas.filter((e) => e.contains(foco)) : [];
    if (comFoco.length) return comFoco[comFoco.length - 1];
    return etapas.find((e) => !this.completa(e)) || null;
  }

  atualizar() {
    const etapas = this.etapas();
    const alvo = this.alvo();
    const caixa = this.raiz.getBoundingClientRect();
    // A linha cobre a etapa da vez inteira: termina no começo da seguinte. Sem seguinte
    // (nada mais a preencher), vai até a base da folha e fecha curvando no canto.
    const seguinte = alvo ? etapas[etapas.indexOf(alvo) + 1] : undefined;
    const fim = seguinte ? seguinte.getBoundingClientRect().top - caixa.top : caixa.height;
    this.linha.hidden = fim <= 0;
    this.linha.style.height = `${Math.max(0, fim)}px`;
    this.linha.classList.toggle("documento__guia--fim", !seguinte);
  }
}

document.querySelectorAll(".documento").forEach((d) => {
  new Guia(/** @type {HTMLElement} */ (d));
});
