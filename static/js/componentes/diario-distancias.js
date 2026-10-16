// @ts-check
/**
 * Diário de bordo: "Preencher pelas distâncias" (`[data-preencher-distancias]`). A partir
 * do km de saída do primeiro trecho, a chegada de cada trecho é sugerida pela distância
 * prevista (`data-prevista` na linha) e a saída do seguinte continua de onde parou. Só
 * escreve nos campos vazios; o autosave grava como se fosse digitação.
 */

/** @param {HTMLInputElement} campo @param {number} valor */
function escrever(campo, valor) {
  campo.value = String(Math.round(valor));
  campo.dispatchEvent(new Event("input", { bubbles: true }));
}

document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {Element} */ (e.target).closest("[data-preencher-distancias]"));
  if (!botao) return;
  const tabela = document.getElementById(botao.dataset.preencherDistancias || "");
  if (!tabela) return;
  let atual = NaN;
  for (const linha of tabela.querySelectorAll("[data-prevista]")) {
    const prevista = Number(linha.getAttribute("data-prevista"));
    const saida = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[name$='-km_inicial']"));
    const chegada = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[name$='-km_final']"));
    if (!saida || !chegada) continue;
    if (saida.value.trim() === "" && Number.isFinite(atual)) escrever(saida, atual);
    const inicio = Number(saida.value);
    if (!Number.isFinite(inicio) || saida.value.trim() === "") { atual = NaN; continue; }
    if (chegada.value.trim() === "" && prevista > 0) escrever(chegada, inicio + prevista);
    const fim = Number(chegada.value);
    atual = Number.isFinite(fim) && chegada.value.trim() !== "" ? fim : NaN;
  }
  const primeiro = /** @type {HTMLInputElement | null} */ (tabela.querySelector("input[name$='-km_inicial']"));
  if (primeiro && primeiro.value.trim() === "") primeiro.focus();
});

export {};
