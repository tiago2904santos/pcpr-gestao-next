// @ts-check
/**
 * Botão "Copiar" de um campo de texto: `<button data-copiar-alvo="<id>">` copia o valor do
 * campo (ou o texto do elemento) para a área de transferência e diz "Copiado" por um
 * instante (o anúncio vai para o leitor de tela pelo `aria-live` do próprio botão). Sem a
 * API de área de transferência (página sem HTTPS), seleciona o texto para o Ctrl+C.
 * Carregado pela tela que o usa (bloco `modulos`); UI Lab §20.
 */

/** @param {HTMLButtonElement} botao @param {string} texto */
function avisar(botao, texto) {
  const rotulo = botao.querySelector("[data-copiar-rotulo]");
  if (!rotulo) return;
  const antes = rotulo.textContent;
  rotulo.textContent = texto;
  window.setTimeout(() => { rotulo.textContent = antes; }, 1800);
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
      campo.focus();
      campo.select();
      avisar(botao, "Selecionado — use Ctrl+C");
    }
  }
});
