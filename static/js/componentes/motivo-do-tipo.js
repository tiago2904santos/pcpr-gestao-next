// @ts-check
/**
 * Tipo da viagem com motivo cadastrado (Cadastros › Tipos de viagem): marcar o tipo escreve
 * o motivo dele no campo Motivo, se o campo está em branco. Desmarcar o tipo cujo motivo
 * está lá intacto apaga o texto (ou põe o de outro tipo marcado). O que a pessoa escreveu
 * nunca é trocado.
 *
 * O campo recebe `input`, então o autosave e o aviso de alterações reagem como a digitação.
 * O servidor faz o mesmo quando a tela não tem JavaScript (viagem.salvar_dados).
 */

/** @param {HTMLElement} raiz */
function ligar(raiz) {
  if (raiz.dataset.pronto) return;
  raiz.dataset.pronto = "1";
  const alvo = /** @type {HTMLTextAreaElement | null} */ (document.getElementById(raiz.dataset.alvo || ""));
  if (!alvo) return;
  /** @type {Record<string, string>} */
  let motivos = {};
  try {
    motivos = JSON.parse(raiz.dataset.motivosDosTipos || "{}");
  } catch {
    return;
  }
  const marcados = () => Array.from(raiz.querySelectorAll("input[type='checkbox']:checked"))
    .map((c) => /** @type {HTMLInputElement} */ (c).value);
  /** @param {string} texto */
  const escrever = (texto) => {
    alvo.value = texto;
    alvo.dispatchEvent(new Event("input", { bubbles: true }));
  };

  raiz.addEventListener("change", (e) => {
    const caixa = e.target;
    if (!(caixa instanceof HTMLInputElement) || caixa.type !== "checkbox") return;
    const atual = alvo.value.trim();
    const deste = (motivos[caixa.value] || "").trim();
    if (caixa.checked) {
      if (!atual && deste) escrever(motivos[caixa.value]);
      return;
    }
    // Desmarcou: só mexe se o motivo é exatamente o deste tipo (a pessoa não o mudou).
    if (deste && atual === deste) {
      const outro = marcados().map((id) => motivos[id]).find(Boolean);
      escrever(outro || "");
    }
  });
}

document.querySelectorAll("[data-motivos-dos-tipos]").forEach((r) => ligar(/** @type {HTMLElement} */ (r)));
document.body.addEventListener("htmx:afterSwap", () => {
  document.querySelectorAll("[data-motivos-dos-tipos]").forEach((r) => ligar(/** @type {HTMLElement} */ (r)));
});

export {};
