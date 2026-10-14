// @ts-check
/**
 * Botão "Copiar" de um campo de texto: `<button data-copiar-alvo="<id>">` copia o valor do
 * campo (ou o texto do elemento) para a área de transferência e diz "Copiado" por um
 * instante (o anúncio vai para o leitor de tela pelo `aria-live` do próprio botão). Sem a
 * API de área de transferência (página sem HTTPS), seleciona o texto para o Ctrl+C.
 * Carregado pela tela que o usa ou sob demanda (app.js); UI Lab §20.
 */

/** @param {HTMLButtonElement} botao @param {string} texto */
function avisar(botao, texto) {
  const rotulo = botao.querySelector("[data-copiar-rotulo]");
  if (!rotulo) return;
  const antes = rotulo.textContent;
  rotulo.textContent = texto;
  botao.toggleAttribute("data-copiado", texto === "Copiado");
  window.setTimeout(() => { rotulo.textContent = antes; botao.removeAttribute("data-copiado"); }, 1800);
}

document.addEventListener("click", async (evento) => {
  const alvo = /** @type {HTMLElement} */ (evento.target);
  const botao = /** @type {HTMLButtonElement | null} */ (alvo.closest("[data-copiar-alvo]"));
  if (!botao) return;
  evento.preventDefault();
  const campo = document.getElementById(botao.dataset.copiarAlvo || "");
  if (!campo) return;
  const texto = campo instanceof HTMLInputElement || campo instanceof HTMLTextAreaElement
    ? campo.value : (campo.textContent || "");
  try {
    await navigator.clipboard.writeText(texto);
    avisar(botao, "Copiado");
  } catch {
    if (campo instanceof HTMLInputElement || campo instanceof HTMLTextAreaElement) {
      const selecao = document.getElementById(botao.dataset.copiarRevelar || "");
      if (selecao) selecao.hidden = false;
      campo.focus();
      campo.select();
      avisar(botao, "Selecionado — use Ctrl+C");
    }
  }
});

// Autosave e HTMX atualizam os valores mantendo a escolha de abrir a divulgação.
/** @type {Map<string, boolean>} */
const divulgacoes = new Map();
document.addEventListener("toggle", (evento) => {
  const alvo = evento.target;
  if (alvo instanceof HTMLDetailsElement && alvo.matches("[data-dados-eprotocolo][id]")) {
    divulgacoes.set(alvo.id, alvo.open);
  }
}, true);
function restaurarDivulgacoes() {
  document.querySelectorAll("details[data-dados-eprotocolo][id]").forEach((alvo) => {
    if (alvo instanceof HTMLDetailsElement && divulgacoes.has(alvo.id)) {
      alvo.open = divulgacoes.get(alvo.id) === true;
    }
  });
}
document.body.addEventListener("htmx:afterSwap", restaurarDivulgacoes);
document.addEventListener("pcpr:pagina-refeita", restaurarDivulgacoes);

/** @type {Map<string, {id: string, copiarAlvo: string}>} */
const focosDaTroca = new Map();
document.body.addEventListener("htmx:oobBeforeSwap", (evento) => {
  const alvo = /** @type {CustomEvent} */ (evento).detail?.target;
  const foco = document.activeElement;
  if (!(alvo instanceof HTMLElement) || !alvo.querySelector("[data-dados-eprotocolo]")
      || !(foco instanceof HTMLElement) || !alvo.contains(foco)) return;
  focosDaTroca.set(alvo.id, { id: foco.id, copiarAlvo: foco.dataset.copiarAlvo || "" });
});
document.body.addEventListener("htmx:oobAfterSwap", (evento) => {
  restaurarDivulgacoes();
  const id = /** @type {CustomEvent} */ (evento).detail?.target?.id;
  const antes = focosDaTroca.get(id);
  if (!antes) return;
  focosDaTroca.delete(id);
  const caixa = document.getElementById(id);
  const novo = antes.id ? document.getElementById(antes.id)
    : caixa?.querySelector(`[data-copiar-alvo="${CSS.escape(antes.copiarAlvo)}"]`);
  if (novo instanceof HTMLElement && caixa?.contains(novo)) {
    const escondido = novo.closest("[hidden]");
    if (escondido instanceof HTMLElement) escondido.hidden = false;
    novo.focus({ preventScroll: true });
  }
});

export {};
