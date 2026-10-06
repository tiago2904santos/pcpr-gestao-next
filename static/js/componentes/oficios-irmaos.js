// @ts-check
/**
 * Ofícios da mesma ação: ao vincular um ofício (termo, OS, plano), se há outros que usam o
 * mesmo roteiro ou estão na mesma viagem, a tela pergunta se eles entram também — "Sim"
 * acrescenta todos de uma vez (cada um preenche o que precisa, como se escolhido na busca).
 *
 * Os irmãos vêm da mesma busca dos ofícios (viagens:buscar_oficios com `irmaos=1` e os já
 * escolhidos em `excluir`).
 */

import { confirmar } from "./dialogo.js";

/** @typedef {{id: string, titulo: string, meta?: string, motivo?: string}} Oficio */

/** @param {Oficio[]} irmaos @param {string} escolhido */
function mensagem(irmaos, escolhido) {
  if (irmaos.length === 1) {
    return `O ${irmaos[0].titulo} ${irmaos[0].motivo || "é da mesma ação"} que o ${escolhido}: `
      + "vinculados, o documento une as datas, os destinos e a equipe dos dois.";
  }
  const nomes = irmaos.map((o) => o.titulo.replace("Ofício ", "")).join(", ");
  return `Os Ofícios ${nomes} são da mesma ação que o ${escolhido} (mesma viagem ou mesmo `
    + "roteiro): vinculados, o documento une as datas, os destinos e a equipe de todos.";
}

document.addEventListener("pc-escolhido", async (evento) => {
  const multi = /** @type {any} */ (/** @type {HTMLElement} */ (evento.target)
    .closest("pc-multiescolha[data-variante='oficios']"));
  // Os que a própria pergunta acrescenta não perguntam de novo.
  if (!multi || multi.dataset.vinculandoIrmaos) return;
  const busca = /** @type {HTMLElement | null} */ (multi.querySelector("pc-combobox[data-fonte-base]"));
  const base = busca?.dataset.fonteBase;
  if (!base) return;
  const ids = Array.from(multi.querySelectorAll(".multiescolha__item"),
    (i) => /** @type {HTMLElement} */ (i).dataset.id).filter(Boolean);
  let irmaos = /** @type {Oficio[]} */ ([]);
  try {
    const r = await fetch(`${base}?excluir=${ids.join(",")}&irmaos=1`,
      { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (r.ok) irmaos = (await r.json()).resultados || [];
  } catch { return; }
  if (!irmaos.length) return;
  const escolhido = /** @type {CustomEvent} */ (evento).detail?.titulo || "ofício escolhido";
  const sim = await confirmar({
    titulo: irmaos.length === 1 ? `Vincular também o ${irmaos[0].titulo}?` : "Vincular os outros ofícios da mesma ação?",
    mensagem: mensagem(irmaos, escolhido),
    confirmar: irmaos.length === 1 ? "Sim, vincular" : `Sim, vincular os ${irmaos.length}`,
    cancelar: "Não",
  });
  if (!sim) return;
  multi.dataset.vinculandoIrmaos = "1";
  try {
    for (const o of irmaos) multi.adicionar(o);
  } finally {
    delete multi.dataset.vinculandoIrmaos;
  }
});

export {};
