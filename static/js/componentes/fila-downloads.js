// @ts-check
/** Fila compartilhada: três requisições simultâneas, falhas e repetição por arquivo. */
/** @typedef {{nome: string, url: string, metodo?: string, dados?: Record<string,string>}} Pedido */
/** @type {Array<{pedido: Pedido, estado: string, abortar: AbortController | null, linha: HTMLElement, status: HTMLElement, repetir: HTMLButtonElement}>} */
const trabalhos = [];
let ativos = 0;
function janela() { return /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-fila-downloads")); }
function abrir() { const d = janela(); if (d && !d.open) d.showModal(); }
function resumo() {
  const status = document.querySelector("[data-fila-status]");
  const concluidos = trabalhos.filter((t) => t.estado === "pronto").length;
  const falhas = trabalhos.filter((t) => t.estado === "falhou").length;
  if (status) status.textContent = `${concluidos} de ${trabalhos.length} enviados ao navegador. ${ativos} em preparação.${falhas ? ` ${falhas} precisam de nova tentativa.` : ""}`;
}
/** @param {Response} resposta */
export async function salvarResposta(resposta) {
  if (!resposta.ok || resposta.redirected || !/attachment|inline/i.test(resposta.headers.get("Content-Disposition") || "")) {
    let mensagem = "Não foi possível preparar o arquivo. Confira o documento e tente novamente.";
    if (resposta.headers.get("Content-Type")?.includes("application/json")) {
      const dados = await resposta.json(); if (dados.erro) mensagem = dados.erro;
    }
    throw new Error(mensagem);
  }
  const disposicao = resposta.headers.get("Content-Disposition") || "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposicao);
  const nome = utf8 ? decodeURIComponent(utf8[1]) : /filename="?([^";]+)"?/i.exec(disposicao)?.[1] || "documento";
  const url = URL.createObjectURL(await resposta.blob());
  const link = document.createElement("a"); link.href = url; link.download = nome;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
function bombear() {
  while (ativos < 3) {
    const trabalho = trabalhos.find((t) => t.estado === "fila");
    if (!trabalho) break;
    trabalho.estado = "gerando"; trabalho.abortar = new AbortController(); ativos++;
    trabalho.status.textContent = "Preparando…"; trabalho.repetir.hidden = true;
    const dados = new FormData();
    for (const [chave, valor] of Object.entries(trabalho.pedido.dados || {})) dados.append(chave, valor);
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
    const metodo = trabalho.pedido.metodo || "GET";
    fetch(trabalho.pedido.url, { method: metodo, credentials: "same-origin",
      body: metodo === "POST" ? dados : undefined, signal: trabalho.abortar.signal,
      headers: { "X-CSRFToken": token, "X-Requested-With": "fetch" },
    }).then(salvarResposta).then(() => {
      trabalho.estado = "pronto"; trabalho.status.textContent = "Enviado ao navegador";
      trabalho.repetir.textContent = "Baixar novamente";
    }).catch((erro) => {
      trabalho.estado = "falhou";
      trabalho.status.textContent = erro.name === "AbortError" ? "Interrompido" : erro.message;
      trabalho.repetir.textContent = "Tentar novamente";
    }).finally(() => {
      ativos--; trabalho.abortar = null; trabalho.repetir.hidden = false; resumo(); bombear();
    });
  }
  resumo();
}
/** @param {Pedido[]} pedidos */
export function executarFila(pedidos) {
  const lista = document.querySelector("[data-fila-itens]");
  if (!lista) throw new Error("A fila não está disponível. Recarregue a página.");
  for (const pedido of pedidos) {
    if (new URL(pedido.url, location.href).origin !== location.origin) continue;
    const linha = document.createElement("li"); linha.className = "cartao";
    const corpo = document.createElement("div"); corpo.className = "cartao__corpo pilha";
    const nome = document.createElement("strong"); nome.textContent = pedido.nome;
    const status = document.createElement("p"); status.textContent = "Na fila"; status.className = "texto-secundario texto-sm";
    const repetir = document.createElement("button"); repetir.type = "button";
    repetir.className = "botao botao--sm"; repetir.textContent = "Tentar novamente"; repetir.hidden = true;
    const trabalho = { pedido, estado: "fila", abortar: null, linha, status, repetir };
    repetir.addEventListener("click", () => { trabalho.estado = "fila"; bombear(); });
    corpo.append(nome, status, repetir); linha.append(corpo); lista.append(linha); trabalhos.push(trabalho);
  }
  abrir(); bombear();
}
document.querySelector("[data-fila-cancelar]")?.addEventListener("click", () => {
  for (const t of trabalhos) {
    if (t.estado === "fila") { t.estado = "falhou"; t.status.textContent = "Interrompido"; t.repetir.hidden = false; }
    t.abortar?.abort();
  }
  resumo();
});
document.addEventListener("click", (e) => {
  if (e.target instanceof Element && e.target.closest("[data-fila-abrir]")) abrir();
});
const manifesto = document.getElementById("manifesto-downloads");
if (manifesto) executarFila(JSON.parse(manifesto.textContent || "{}").fila || []);
