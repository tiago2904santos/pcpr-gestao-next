// @ts-check
/**
 * Texto pronto (componentes/texto_pronto.html): escolher um texto preenche a área de texto
 * na hora. Se ela já tem outro texto, pergunta antes de substituir — nunca apaga o que a
 * pessoa escreveu sem ela concordar. "Guardar como texto pronto" leva o texto do campo para
 * o catálogo (cadastros:salvar_texto) e o deixa escolhido.
 *
 * O campo recebe `input` ao ser preenchido, então o autosave e o aviso de "alterações não
 * salvas" reagem como se a pessoa tivesse digitado.
 *
 * Com `data-somar` (observação do despacho de Eventos, como na referência), cada texto
 * escolhido entra numa linha nova no fim do campo — sem repetir o que já está lá — e a
 * escolha volta a "Escrever do zero" para somar o próximo.
 */

import { confirmar, fecharDialogo } from "./dialogo.js";

/** @param {string} mensagem @param {string} [nivel] */
function avisar(mensagem, nivel = "sucesso") {
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel } }));
}

/** Escolher um texto pronto preenche o campo (perguntando antes de trocar texto escrito).
 * @param {HTMLTextAreaElement} alvo @param {HTMLSelectElement} escolha */
function ligarEscolha(alvo, escolha) {
  /** Textos de todas as opções: o campo com um deles, sem ajuste, é texto pronto intacto. */
  const prontos = () => new Set(Array.from(escolha.options)
    .map((o) => (o.dataset.texto || "").trim()).filter(Boolean));
  // O campo já veio com um texto pronto (ex.: o motivo padrão do ofício novo): a escolha
  // mostra qual é, em vez de "Escrever do zero".
  const deCasa = Array.from(escolha.options).find(
    (o) => o.dataset.texto && o.dataset.texto.trim() === alvo.value.trim());
  if (deCasa && !escolha.value) escolha.value = deCasa.value;
  let anterior = escolha.value;
  if (deCasa) escolha.dispatchEvent(new Event("change", { bubbles: true }));

  escolha.addEventListener("change", async () => {
    if (escolha.value === anterior) return; // volta programática (Cancelar) ou nada mudou
    const texto = escolha.selectedOptions[0]?.dataset.texto;
    if (!texto) { anterior = escolha.value; return; }
    const atual = alvo.value.trim();
    // Só pergunta quando há texto escrito à mão (ou ajustado): trocar um texto pronto
    // intacto por outro não apaga trabalho de ninguém.
    if (atual && atual !== texto.trim() && !prontos().has(atual)) {
      const ok = await confirmar({
        titulo: "Substituir o texto?",
        mensagem: "O campo já tem um texto. Ele será trocado pelo texto pronto escolhido.",
        confirmar: "Substituir",
      });
      if (!ok) {
        escolha.value = anterior; // volta a escolha (e o botão do pc-select acompanha)
        escolha.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
    }
    anterior = escolha.value;
    alvo.value = texto;
    alvo.dispatchEvent(new Event("input", { bubbles: true }));
    alvo.focus();
  });
}

/** Somar: o texto escolhido vai para o fim do campo, numa linha nova (sem repetir).
 * @param {HTMLTextAreaElement} alvo @param {HTMLSelectElement} escolha */
function ligarSoma(alvo, escolha) {
  escolha.addEventListener("change", () => {
    const texto = (escolha.selectedOptions[0]?.dataset.texto || "").trim();
    if (!texto) return;
    const atual = alvo.value.trim();
    if (!atual.includes(texto)) {
      alvo.value = atual ? `${atual}\n${texto}` : texto;
      alvo.dispatchEvent(new Event("input", { bubbles: true }));
    }
    escolha.value = "";
    escolha.dispatchEvent(new Event("change", { bubbles: true }));
    alvo.focus();
  });
}

/** @param {HTMLElement} raiz */
function ligar(raiz) {
  if (raiz.dataset.pronto) return;
  raiz.dataset.pronto = "1";
  const alvo = /** @type {HTMLTextAreaElement | null} */ (
    document.getElementById(raiz.dataset.alvo || ""));
  if (!alvo) return;
  // Sem nenhum texto pronto cadastrado a escolha nem aparece; o "Guardar texto" continua.
  const escolha = /** @type {HTMLSelectElement | null} */ (raiz.querySelector("select"));
  if (escolha && "somar" in raiz.dataset) ligarSoma(alvo, escolha);
  else if (escolha) ligarEscolha(alvo, escolha);
  const guardar = /** @type {HTMLButtonElement | null} */ (raiz.querySelector("[data-guardar-texto]"));
  const janela = /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-guardar-texto"));
  if (!guardar || !janela) return;
  // Só há o que guardar quando o campo tem texto: vazio, o botão nem aparece.
  const mostrarGuardar = () => { guardar.hidden = !alvo.value.trim(); };
  mostrarGuardar();
  alvo.addEventListener("input", mostrarGuardar);
  guardar.addEventListener("click", () => {
    const texto = alvo.value.trim();
    if (!texto) {
      avisar("Escreva o texto no campo antes de guardá-lo.", "aviso");
      alvo.focus();
      return;
    }
    const form = /** @type {HTMLFormElement} */ (janela.querySelector("form"));
    /** @type {HTMLInputElement} */ (form.elements.namedItem("tipo")).value = raiz.dataset.tipo || "";
    /** @type {HTMLInputElement} */ (form.elements.namedItem("texto")).value = texto;
    /** @type {HTMLElement} */ (form.querySelector("[data-guardar-texto-previa]")).textContent = texto;
    const nome = /** @type {HTMLInputElement} */ (form.elements.namedItem("nome"));
    nome.value = "";
    mostrarErro(form, "");
    janela.dataset.origem = raiz.dataset.alvo || "";
    janela.showModal();
    nome.focus();
  });
}

/** @param {HTMLFormElement} form @param {string} mensagem */
function mostrarErro(form, mensagem) {
  const erro = /** @type {HTMLElement} */ (form.querySelector("#guardar-texto-erro"));
  const nome = /** @type {HTMLInputElement} */ (form.elements.namedItem("nome"));
  erro.textContent = mensagem;
  erro.hidden = !mensagem;
  if (mensagem) nome.setAttribute("aria-invalid", "true");
  else nome.removeAttribute("aria-invalid");
  nome.closest(".campo")?.classList.toggle("campo--erro", Boolean(mensagem));
}

const janela = /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-guardar-texto"));
janela?.querySelector("form")?.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const form = /** @type {HTMLFormElement} */ (evento.currentTarget);
  const nome = /** @type {HTMLInputElement} */ (form.elements.namedItem("nome"));
  if (!nome.value.trim()) {
    mostrarErro(form, "Dê um nome curto ao texto pronto.");
    nome.focus();
    return;
  }
  const resposta = await fetch(form.action, {
    method: "POST", body: new FormData(form), credentials: "same-origin",
    headers: { Accept: "application/json", "X-Requested-With": "fetch" },
  }).catch(() => null);
  const corpo = resposta ? await resposta.json().catch(() => ({})) : {};
  if (!resposta || !resposta.ok) {
    mostrarErro(form, corpo.erro || "Não foi possível guardar agora. Tente de novo.");
    nome.focus();
    return;
  }
  // Entra na escolha do campo que pediu, já selecionado (o texto do campo não muda).
  const raiz = document.querySelector(`[data-texto-pronto][data-alvo="${janela.dataset.origem}"]`);
  const escolha = /** @type {HTMLSelectElement | null} */ (raiz?.querySelector("select") ?? null);
  if (escolha) {
    const opcao = new Option(corpo.nome, String(corpo.id), true, true);
    opcao.dataset.texto = corpo.texto;
    escolha.add(opcao);
    escolha.dispatchEvent(new Event("change", { bubbles: true }));
  }
  fecharDialogo(janela);
  avisar(`Texto pronto “${corpo.nome}” guardado.`);
});

document.querySelectorAll("[data-texto-pronto]").forEach((r) => ligar(/** @type {HTMLElement} */ (r)));
document.body.addEventListener("htmx:afterSwap", () => {
  document.querySelectorAll("[data-texto-pronto]").forEach((r) => ligar(/** @type {HTMLElement} */ (r)));
});
