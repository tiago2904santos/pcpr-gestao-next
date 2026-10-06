// @ts-check
/**
 * Links que geram um arquivo na hora (`<a data-baixar-arquivo href="…pdf">`): gerar o PDF
 * leva alguns segundos, e um link comum não dá sinal nenhum nesse tempo — parecia que o
 * botão nem funcionava. Aqui o clique busca o arquivo por fetch enquanto o botão mostra
 * "processando" (aria-busy: o indicador gira no lugar do texto; components.css), baixa
 * ao chegar e confirma ("concluído", verde por um instante).
 *
 * Também vale para `<form data-baixar-arquivo>` (POST: ex. "Baixar separados", um ZIP):
 * o botão que enviou mostra o processando.
 *
 * Num item de menu, quem mostra o processando é o botão do menu (⋮). Se o servidor
 * responder com uma página (ex.: um aviso de que falta configuração), a navegação segue
 * para ela. Ctrl/⌘+clique e sem JavaScript: o link comum.
 */

/** @param {string} mensagem @param {string} [nivel] */
function avisar(mensagem, nivel = "erro") {
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel } }));
}

/** @param {Response} resposta @param {string} padrao */
function nomeDoArquivo(resposta, padrao) {
  const disposicao = resposta.headers.get("Content-Disposition") || "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposicao);
  if (utf8) return decodeURIComponent(utf8[1]);
  const simples = /filename="?([^";]+)"?/i.exec(disposicao);
  return simples ? simples[1] : padrao;
}

/**
 * Busca o arquivo com o botão em "processando" e baixa ao chegar.
 * @param {HTMLElement | null} botao @param {string} url @param {RequestInit} pedido
 * @param {string} padrao nome do arquivo se o servidor não disser
 */
async function gerar(botao, url, pedido, padrao) {
  if (botao?.getAttribute("aria-busy") === "true") return;  // já está gerando
  botao?.setAttribute("aria-busy", "true");
  try {
    const resposta = await fetch(url, { credentials: "same-origin", ...pedido });
    const tipo = resposta.headers.get("Content-Type") || "";
    if (resposta.redirected || tipo.includes("text/html")) {
      window.location.href = resposta.url;  // o servidor mandou uma página (aviso)
      return;
    }
    if (!resposta.ok) throw new Error(String(resposta.status));
    const arquivo = URL.createObjectURL(await resposta.blob());
    const baixar = document.createElement("a");
    baixar.href = arquivo;
    baixar.download = nomeDoArquivo(resposta, padrao);
    document.body.append(baixar);
    baixar.click();
    baixar.remove();
    window.setTimeout(() => URL.revokeObjectURL(arquivo), 10_000);
    if (botao) {
      botao.dataset.estado = "concluido";
      window.setTimeout(() => { delete botao.dataset.estado; }, 1600);
    }
  } catch {
    avisar("Não foi possível gerar o arquivo agora. Tente de novo.");
  } finally {
    botao?.removeAttribute("aria-busy");
  }
}

document.addEventListener("click", (evento) => {
  const link = /** @type {HTMLAnchorElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("a[data-baixar-arquivo]"));
  if (!link || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) return;
  evento.preventDefault();
  const menu = /** @type {any} */ (link.closest("pc-menu"));
  const botao = /** @type {HTMLElement | null} */ (link.classList.contains("botao")
    ? link : menu?.querySelector("[data-menu-botao]") ?? null);
  if (menu && typeof menu.fechar === "function") menu.fechar(false);
  gerar(botao, link.href, {}, link.getAttribute("download") || "documento");
});

document.addEventListener("submit", (evento) => {
  const form = /** @type {HTMLFormElement} */ (evento.target);
  if (!form.matches("form[data-baixar-arquivo]")) return;
  evento.preventDefault();
  const botao = /** @type {HTMLElement | null} */ (
    evento.submitter || form.querySelector("[type=submit]"));
  gerar(botao, form.action, {
    method: "POST", body: new FormData(form), headers: { "X-Requested-With": "fetch" },
  }, "documentos.zip");
});

export {};
