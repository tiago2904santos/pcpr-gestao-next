// @ts-check
/**
 * Diálogos com <dialog> nativo (foco preso, Esc e véu já acessíveis).
 *
 *  - `<button data-abrir-dialogo="id">` abre o <dialog id="id">;
 *  - `<button data-fechar-dialogo>` dentro do diálogo fecha;
 *  - Confirmações do HTMX (`hx-confirm`) usam o diálogo #dialogo-confirmacao
 *    em vez do window.confirm (que não segue o Design System).
 *  - Formulários comuns com `data-confirmar="Mensagem"` também passam pelo diálogo.
 */

/** @param {string} id */
function dialogoPorId(id) {
  return /** @type {HTMLDialogElement | null} */ (document.getElementById(id));
}

document.addEventListener("click", (e) => {
  const alvo = /** @type {HTMLElement} */ (e.target);
  const abrir = /** @type {HTMLElement | null} */ (alvo.closest("[data-abrir-dialogo]"));
  if (abrir) {
    const d = dialogoPorId(abrir.dataset.abrirDialogo || "");
    if (d) {
      e.preventDefault();
      d.showModal();
    }
    return;
  }
  const fechar = alvo.closest("[data-fechar-dialogo]");
  if (fechar) fechar.closest("dialog")?.close();
});

/**
 * Abre o diálogo de confirmação padrão e resolve com true/false.
 * @param {{titulo?: string, mensagem: string, confirmar?: string, perigo?: boolean}} opcoes
 * @returns {Promise<boolean>}
 */
export function confirmar(opcoes) {
  const d = dialogoPorId("dialogo-confirmacao");
  if (!d) return Promise.resolve(window.confirm(opcoes.mensagem));
  const titulo = /** @type {HTMLElement} */ (d.querySelector("[data-titulo]"));
  const mensagem = /** @type {HTMLElement} */ (d.querySelector("[data-mensagem]"));
  const botao = /** @type {HTMLButtonElement} */ (d.querySelector("[data-confirmar]"));
  titulo.textContent = opcoes.titulo || "Confirmar ação";
  mensagem.textContent = opcoes.mensagem;
  botao.textContent = opcoes.confirmar || "Confirmar";
  d.classList.toggle("dialogo--perigo", Boolean(opcoes.perigo));
  botao.classList.toggle("botao--perigo", Boolean(opcoes.perigo));
  botao.classList.toggle("botao--primario", !opcoes.perigo);
  return new Promise((resolver) => {
    d.addEventListener("close", () => resolver(d.returnValue === "confirmar"), { once: true });
    d.returnValue = "";
    d.showModal();
  });
}

document.addEventListener("htmx:confirm", (evento) => {
  const e = /** @type {CustomEvent} */ (evento);
  const pergunta = e.detail.question;
  if (!pergunta) return;
  e.preventDefault();
  const origem = /** @type {HTMLElement} */ (e.detail.elt);
  confirmar({
    titulo: origem.dataset.confirmarTitulo,
    mensagem: pergunta,
    confirmar: origem.dataset.confirmarRotulo,
    perigo: origem.dataset.confirmarPerigo !== undefined,
  }).then((ok) => {
    if (ok) e.detail.issueRequest(true);
  });
});

document.addEventListener("submit", (evento) => {
  const form = /** @type {HTMLFormElement} */ (evento.target);
  const submissor = /** @type {HTMLElement | null} */ (
    /** @type {SubmitEvent} */ (evento).submitter
  );
  const fonte = submissor?.dataset.confirmar ? submissor : form;
  const mensagem = fonte.dataset.confirmar;
  if (!mensagem || form.dataset.confirmado === "1") return;
  evento.preventDefault();
  confirmar({
    titulo: fonte.dataset.confirmarTitulo,
    mensagem,
    confirmar: fonte.dataset.confirmarRotulo,
    perigo: fonte.dataset.confirmarPerigo !== undefined,
  }).then((ok) => {
    if (!ok) return;
    form.dataset.confirmado = "1";
    form.requestSubmit(/** @type {HTMLButtonElement | null} */ (submissor));
    delete form.dataset.confirmado;
  });
});
