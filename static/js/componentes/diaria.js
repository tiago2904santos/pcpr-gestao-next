// @ts-check
/**
 * Prévia dos percentuais da diária enquanto se digita o valor de 24 h
 * (`input[data-diaria-base]`): preenche `[data-diaria-percentual="15"]` e `"30"` do mesmo
 * formulário. Só conforto: quem calcula de verdade é o servidor (mesmo arredondamento,
 * meio centavo para cima).
 */

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** @param {HTMLInputElement} campo */
function atualizar(campo) {
  const form = campo.form;
  if (!form) return;
  const centavos = Math.round(Number(String(campo.value).replace(",", ".")) * 100);
  form.querySelectorAll("[data-diaria-percentual]").forEach((saida) => {
    const pct = Number(/** @type {HTMLElement} */ (saida).dataset.diariaPercentual);
    // Inteiros em centavos evitam o erro de ponto flutuante (290,55 × 15% = 43,5825 → 43,58).
    const valor = Number.isFinite(centavos) && centavos > 0
      ? Math.floor((centavos * pct + 50) / 100) / 100 : null;
    saida.textContent = valor === null ? "—" : moeda.format(valor);
  });
}

document.addEventListener("input", (e) => {
  const campo = /** @type {HTMLElement} */ (e.target);
  if (campo instanceof HTMLInputElement && campo.matches("[data-diaria-base]")) atualizar(campo);
});
document.querySelectorAll("input[data-diaria-base]").forEach((c) => atualizar(/** @type {HTMLInputElement} */ (c)));

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
