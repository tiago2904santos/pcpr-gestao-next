// @ts-check
/**
 * Equipe do cadastro novo (`[data-equipe-local]`): o servidor escolhido no combobox entra
 * na lista como inputs do formulário (`equipe`, `motorista`) — nada é gravado até o ofício
 * ser salvo. Na edição, a equipe continua sendo salva na hora pelo servidor (HTMX).
 */

/** @param {HTMLElement} secao @param {string} texto */
function anunciar(secao, texto) {
  const alvo = secao.querySelector("[data-equipe-anuncio]");
  if (alvo) alvo.textContent = texto;
}

/** @param {HTMLElement} secao */
function atualizar(secao) {
  const n = secao.querySelectorAll("[data-equipe-lista] > li").length;
  const contagem = secao.querySelector("[data-equipe-contagem]");
  if (contagem) contagem.textContent = `${n} ${n === 1 ? "servidor" : "servidores"}`;
  const vazia = /** @type {HTMLElement | null} */ (secao.querySelector("[data-equipe-vazia]"));
  if (vazia) vazia.hidden = n > 0;
}

/** @param {string} nome */
function iniciais(nome) {
  const partes = nome.trim().split(/\s+/);
  const primeira = partes[0]?.[0] || "";
  const ultima = partes.length > 1 ? partes[partes.length - 1][0] : "";
  return (primeira + ultima).toUpperCase();
}

/** Marca o formulário protegido como "sujo" (protecao.js escuta change). @param {Element} el */
function sujar(el) {
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

document.addEventListener("pc-selecionado", (evento) => {
  const secao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("[data-equipe-local]")
  );
  if (!secao) return;
  const opcao = /** @type {CustomEvent} */ (evento).detail || {};
  const lista = secao.querySelector("[data-equipe-lista]");
  const modelo = /** @type {HTMLTemplateElement | null} */ (secao.querySelector("template[data-equipe-modelo]"));
  if (!lista || !modelo || !opcao.id) return;
  if (lista.querySelector(`[data-servidor="${CSS.escape(String(opcao.id))}"]`)) {
    anunciar(secao, `${opcao.titulo} já está na equipe.`);
    return;
  }
  const li = /** @type {HTMLElement} */ (modelo.content.firstElementChild?.cloneNode(true));
  li.dataset.servidor = String(opcao.id);
  /** @param {string} sel @param {string} texto */
  const texto = (sel, texto) => {
    const el = li.querySelector(sel);
    if (el) el.textContent = texto;
  };
  texto("[data-iniciais]", iniciais(opcao.titulo || ""));
  texto("[data-nome]", opcao.titulo || "");
  texto("[data-meta]", opcao.meta || "");
  texto("[data-nome-sr]", `: ${opcao.titulo || ""}`);
  li.querySelector("[data-remover-servidor]")?.setAttribute("aria-label", `Remover ${opcao.titulo} da equipe`);
  const id = /** @type {HTMLInputElement | null} */ (li.querySelector("[data-id]"));
  const motorista = /** @type {HTMLInputElement | null} */ (li.querySelector("[data-motorista]"));
  if (id) id.value = String(opcao.id);
  if (motorista) motorista.value = String(opcao.id);
  lista.append(li);
  atualizar(secao);
  anunciar(secao, `${opcao.titulo} incluído na equipe.`);
  if (id) sujar(id);
});

document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement} */ (evento.target).closest("[data-remover-servidor]");
  const secao = /** @type {HTMLElement | null} */ (botao?.closest("[data-equipe-local]") || null);
  if (!botao || !secao) return;
  const li = botao.closest("li");
  const nome = li?.querySelector("[data-nome]")?.textContent || "Servidor";
  li?.remove();
  atualizar(secao);
  anunciar(secao, `${nome} removido da equipe.`);
  /** @type {HTMLInputElement | null} */ (secao.querySelector("#busca-servidor"))?.focus();
  sujar(secao);
});

// Um motorista por equipe: marcar um desmarca os outros.
document.addEventListener("change", (evento) => {
  const caixa = /** @type {HTMLInputElement} */ (evento.target);
  if (!caixa.matches?.("[data-equipe-local] [data-motorista]") || !caixa.checked) return;
  caixa.closest("[data-equipe-lista]")?.querySelectorAll("[data-motorista]").forEach((outra) => {
    if (outra !== caixa) /** @type {HTMLInputElement} */ (outra).checked = false;
  });
});
