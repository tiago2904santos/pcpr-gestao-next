// @ts-check
/**
 * Botão "limpar" dentro de um campo de texto: o mesmo × dos comboboxes, para a busca das
 * listas e para qualquer campo marcado com `data-limpavel` (ou `type="search"`).
 *
 * Só aparece quando há texto — em campo vazio não cria parada no Tab. Limpar dispara os
 * mesmos eventos de quem apaga à mão, então a busca ao vivo refaz a consulta.
 */
// O ícone do sprite mora em menu.js (carregado em toda página: sem requisição a mais).
import { icone } from "./menu.js";

/**
 * Põe o botão no campo e devolve a função que acerta a visibilidade.
 * @param {HTMLInputElement} entrada
 * @param {() => void} [aoLimpar] o que fazer além de esvaziar (ex.: reabrir a lista)
 */
export function adicionarLimpar(entrada, aoLimpar) {
  let caixa = entrada.parentElement;
  if (!caixa || !caixa.classList.contains("entrada-composta")) {
    caixa = document.createElement("div");
    caixa.className = "entrada-composta";
    entrada.before(caixa);
    caixa.append(entrada);
  }
  caixa.classList.add("entrada-composta--limpavel");
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "entrada-composta__botao";
  botao.title = "Limpar o campo";
  botao.hidden = !entrada.value.trim();
  const rotulo = document.createElement("span");
  rotulo.className = "sr-only";
  rotulo.textContent = "Limpar o campo";
  botao.append(icone("x"), rotulo);
  const sincronizar = () => { botao.hidden = !entrada.value.trim(); };
  botao.addEventListener("click", () => {
    entrada.value = "";
    entrada.dispatchEvent(new Event("input", { bubbles: true }));
    entrada.dispatchEvent(new Event("change", { bubbles: true }));
    entrada.focus();
    sincronizar();
    aoLimpar?.();
  });
  entrada.addEventListener("input", sincronizar);
  entrada.addEventListener("change", sincronizar);
  caixa.append(botao);
  return sincronizar;
}

// Campos de busca das listas: o botão entra sozinho.
document.querySelectorAll("input[type='search'].entrada, input[data-limpavel]").forEach(
  (e) => adicionarLimpar(/** @type {HTMLInputElement} */ (e)));
