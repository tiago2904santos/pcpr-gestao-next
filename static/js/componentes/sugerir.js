// @ts-check
/**
 * Preencher campos de texto a partir do servidor ou de outro registro, sem gravar (quem grava é
 * o autosave, quando o campo recebe `input`). Se o campo já tem outro texto, pergunta antes de
 * substituir — nunca apaga o que a pessoa escreveu sem ela concordar.
 *
 *  - `<button data-sugerir="<url>" data-alvo="<id do campo>" data-form="<id do form>">`:
 *    manda o formulário (o rascunho na tela) por POST e põe no campo o `texto` da resposta
 *    (relatório técnico: "Sugerir texto" da conclusão e das medidas, regra local).
 *  - `<div data-copiar-de="<id do json_script>" data-prefixo="rt-">` com um `<select>` e um
 *    `<button data-copiar>`: copia os textos do registro escolhido para os campos
 *    `#<prefixo><campo>` (relatório técnico: "Copiar de outro RT").
 */

import { confirmar } from "./dialogo.js";

/** @param {string} mensagem @param {string} [nivel] */
function avisar(mensagem, nivel = "sucesso") {
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel } }));
}

/** @param {HTMLTextAreaElement | HTMLInputElement} campo @param {string} texto */
function preencher(campo, texto) {
  campo.value = texto;
  campo.dispatchEvent(new Event("input", { bubbles: true }));
}

/** @param {Array<[HTMLTextAreaElement | HTMLInputElement, string]>} trocas */
async function podeSubstituir(trocas) {
  const sobrescreve = trocas.some(([campo, texto]) => campo.value.trim() && campo.value.trim() !== texto.trim());
  if (!sobrescreve) return true;
  return confirmar({
    titulo: "Substituir o texto?",
    mensagem: "O campo já tem texto. Ele será trocado pela sugestão (você ainda pode desfazer com Ctrl+Z antes de salvar).",
    confirmar: "Substituir",
  });
}

document.addEventListener("click", async (e) => {
  const alvo = /** @type {HTMLElement} */ (e.target);
  const sugerir = /** @type {HTMLButtonElement | null} */ (alvo.closest("[data-sugerir]"));
  if (sugerir) {
    e.preventDefault();
    const campo = /** @type {HTMLTextAreaElement | null} */ (document.getElementById(sugerir.dataset.alvo || ""));
    const form = /** @type {HTMLFormElement | null} */ (document.getElementById(sugerir.dataset.form || ""));
    if (!campo || !form) return;
    sugerir.disabled = true;
    try {
      const resposta = await fetch(sugerir.dataset.sugerir || "", {
        method: "POST", body: new FormData(form), headers: { Accept: "application/json" },
      });
      const corpo = await resposta.json();
      if (!resposta.ok || !corpo.texto) {
        avisar(corpo.erro || "Não foi possível sugerir agora.", "perigo");
        return;
      }
      if (await podeSubstituir([[campo, corpo.texto]])) {
        preencher(campo, corpo.texto);
        campo.focus();
        avisar("Sugestão no campo — revise antes de usar.");
      }
    } catch {
      avisar("Não foi possível sugerir agora.", "perigo");
    } finally {
      sugerir.disabled = false;
    }
    return;
  }
  const copiar = /** @type {HTMLButtonElement | null} */ (alvo.closest("[data-copiar]"));
  const raiz = /** @type {HTMLElement | null} */ (copiar?.closest("[data-copiar-de]") ?? null);
  if (!copiar || !raiz) return;
  e.preventDefault();
  const dados = document.getElementById(raiz.dataset.copiarDe || "");
  const escolha = /** @type {HTMLSelectElement | null} */ (raiz.querySelector("select"));
  if (!dados || !escolha || !escolha.value) {
    avisar("Escolha de qual relatório copiar.", "aviso");
    return;
  }
  /** @type {Array<{id: number, textos: Record<string, string>}>} */
  const lista = JSON.parse(dados.textContent || "[]");
  const item = lista.find((i) => String(i.id) === escolha.value);
  if (!item) return;
  /** @type {Array<[HTMLTextAreaElement | HTMLInputElement, string]>} */
  const trocas = [];
  for (const [nome, texto] of Object.entries(item.textos)) {
    const campo = /** @type {HTMLTextAreaElement | null} */ (document.getElementById(`${raiz.dataset.prefixo || ""}${nome}`));
    if (campo && (texto || "").trim()) trocas.push([campo, texto]);
  }
  if (!trocas.length) return;
  if (await podeSubstituir(trocas)) {
    for (const [campo, texto] of trocas) preencher(campo, texto);
    avisar("Textos copiados — revise antes de usar.");
  }
});
