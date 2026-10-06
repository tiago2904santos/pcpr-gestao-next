// @ts-check
/**
 * Atividades do plano de trabalho: aplicar um conjunto, filtrar por nome e limpar.
 *
 * Marcação: um contêiner [data-conjuntos] com
 *  - <select data-conjunto>, cada <option data-ids="1,2,3"> (as atividades do conjunto);
 *  - <input data-filtro> (busca pelo nome) e um [data-sem-resultado] para "nada achado";
 *  - <button data-limpar>;
 *  - as caixas (.caixas__item com <input type="checkbox">).
 * Aplicar um conjunto SUBSTITUI a seleção; se já havia algo marcado, pede confirmação
 * (referência). Cada mudança avisa o formulário (autosave). Sem JavaScript, as caixas
 * continuam funcionando; só os atalhos somem.
 */

import { confirmar } from "./dialogo.js";

/** @param {HTMLElement} raiz */
function preparar(raiz) {
  const caixas = () => /** @type {HTMLInputElement[]} */ ([...raiz.querySelectorAll(".caixas__item input[type='checkbox']")]);
  const conjunto = /** @type {HTMLSelectElement | null} */ (raiz.querySelector("[data-conjunto]"));
  const filtro = /** @type {HTMLInputElement | null} */ (raiz.querySelector("[data-filtro]"));
  const semResultado = /** @type {HTMLElement | null} */ (raiz.querySelector("[data-sem-resultado]"));
  const anuncio = /** @type {HTMLElement | null} */ (raiz.querySelector("[data-anuncio]"));
  const ferramentas = raiz.querySelector("[data-ferramentas]");
  if (ferramentas) /** @type {HTMLElement} */ (ferramentas).hidden = false;

  const contagem = /** @type {HTMLElement | null} */ (raiz.querySelector("[data-contagem]"));
  // A contagem também aparece no selo do cabeçalho do cartão (fora do contêiner).
  const espelho = /** @type {HTMLElement | null} */ (
    raiz.closest(".secao")?.querySelector("[data-contagem-espelho]") ?? null);
  const contar = () => {
    const n = String(caixas().filter((c) => c.checked).length);
    if (contagem) contagem.textContent = n;
    if (espelho) espelho.textContent = n;
  };
  raiz.addEventListener("change", (e) => {
    if (/** @type {HTMLElement} */ (e.target).matches?.(".caixas__item input")) contar();
  });
  const avisar = () => { contar(); caixas()[0]?.dispatchEvent(new Event("change", { bubbles: true })); };
  /** @param {string} texto */
  const anunciar = (texto) => { if (anuncio) anuncio.textContent = texto; };

  conjunto?.addEventListener("change", async () => {
    const opcao = conjunto.selectedOptions[0];
    const ids = new Set((opcao?.dataset.ids || "").split(",").filter(Boolean));
    if (!ids.size) return;
    const nome = opcao.textContent?.trim() || "";
    if (caixas().some((c) => c.checked)) {
      const ok = await confirmar({
        titulo: "Aplicar conjunto?",
        mensagem: `Aplicar o conjunto “${nome}” vai substituir a seleção atual. Continuar?`,
        confirmar: "Aplicar",
      });
      if (!ok) { conjunto.value = ""; return; }
    }
    for (const c of caixas()) c.checked = ids.has(c.value);
    conjunto.value = "";
    anunciar(`Conjunto ${nome} aplicado: ${ids.size} atividade${ids.size === 1 ? "" : "s"}.`);
    avisar();
  });

  // "+" de conjunto: a janela de cadastro nasce com as atividades marcadas agora no plano.
  raiz.querySelector("[data-abrir-dialogo='dialogo-conjunto']")?.addEventListener("click", () => {
    const marcadas = new Set(caixas().filter((c) => c.checked).map((c) => c.value));
    document.querySelectorAll("#dialogo-conjunto input[name='atividades']").forEach((c) => {
      /** @type {HTMLInputElement} */ (c).checked = marcadas.has(/** @type {HTMLInputElement} */ (c).value);
    });
  });

  raiz.querySelector("[data-limpar]")?.addEventListener("click", async () => {
    const marcadas = caixas().filter((c) => c.checked).length;
    if (!marcadas) return;
    const ok = await confirmar({
      titulo: "Desmarcar todas?",
      mensagem: `As ${marcadas} atividades marcadas saem do plano (e as metas e recursos delas).`,
      confirmar: "Desmarcar",
    });
    if (!ok) return;
    for (const c of caixas()) c.checked = false;
    anunciar("Todas as atividades desmarcadas.");
    avisar();
  });

  filtro?.addEventListener("input", () => {
    const termo = normalizar(filtro.value);
    let visiveis = 0;
    for (const c of caixas()) {
      const item = /** @type {HTMLElement} */ (c.closest(".caixas__item"));
      const casa = !termo || normalizar(item.textContent || "").includes(termo);
      item.hidden = !casa;
      if (casa) visiveis += 1;
    }
    if (semResultado) semResultado.hidden = visiveis > 0;
  });
}

/** @param {string} texto */
function normalizar(texto) {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

document.querySelectorAll("[data-conjuntos]").forEach((r) => preparar(/** @type {HTMLElement} */ (r)));
