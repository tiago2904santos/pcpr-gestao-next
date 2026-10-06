// @ts-check
/**
 * "Gerar" nas folhas de documento (termo, OS — `<a data-gerar-e-voltar="<lista>">`):
 * abre a visualização do documento em outra aba e esta aba volta à lista, depois de gravar
 * o que estiver pendente (autosave), para nada se perder.
 */

// "Gerar" abre a visualização em outra aba e esta aba volta à lista — depois de
// gravar o que estiver pendente, para nada se perder. A aba nova é aberta aqui (e não pelo
// target=_blank do link): há navegadores embutidos que abrem "_blank" na mesma aba, e aí a
// volta à lista nunca acontecia. Aba bloqueada: a visualização abre nesta mesma aba.
document.addEventListener("click", async (evento) => {
  const link = /** @type {HTMLAnchorElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("a[data-gerar-e-voltar]"));
  if (!link || evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey) return;
  evento.preventDefault();
  const nova = window.open(link.href, "_blank");
  if (!nova) {
    // Sem aba nova (bloqueada, ou um navegador embutido que não as abre): a visualização
    // abre aqui, gravado antes, e o "Voltar" dela leva à lista — o mesmo destino.
    try {
      const { Autosave } = await import("./autosave.js");
      await Promise.all(Autosave.todos.map((a) => a.descarregar()));
    } catch { /* segue */ }
    document.dispatchEvent(new CustomEvent("pcpr:dados-salvos"));
    const url = new URL(link.href, window.location.href);
    url.searchParams.set("voltar", "lista");
    window.location.href = url.toString();
    return;
  }
  nova.opener = null;
  const destino = link.dataset.gerarEVoltar || "";
  link.setAttribute("aria-busy", "true");
  try {
    const { Autosave } = await import("./autosave.js");
    await Promise.all(Autosave.todos.map((a) => a.descarregar()));
  } catch {
    /* sem autosave na página: segue */
  }
  // Gravado: a proteção de saída não precisa perguntar nada.
  document.dispatchEvent(new CustomEvent("pcpr:dados-salvos"));
  window.location.href = destino;
});

export {};
