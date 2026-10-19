// @ts-check
/**
 * Link de km vencido sem internet (fluxo 10-4). O service worker apaga a cópia da página da
 * viagem (roteiro e km não ficam no aparelho depois do vencimento) e mostra esta página
 * local no lugar. Ela só lê o que ficou pendente NESTE aparelho — as chaves
 * `pcpr-km:v1:<link>:<trecho>` do `km-offline.js` — para a pessoa copiar e mandar ao setor
 * de viagens (ou digitar no link novo). Nada é enviado nem apagado daqui.
 */

/**
 * @typedef {{linha?: number, chave?: string, rotulo?: string, digitado_em?: string,
 *   estado?: string, campos?: {km_inicial?: number | null, km_final?: number | null}}} Pendente
 */

const raiz = document.querySelector("[data-km-vencido]");
if (raiz instanceof HTMLElement) iniciar(raiz);

/** @param {HTMLElement} raiz */
function iniciar(raiz) {
  const itens = pendentes(`pcpr-km:v1:${raiz.dataset.link || ""}:`);
  const bloco = raiz.querySelector("[data-km-pendentes]");
  const nenhum = raiz.querySelector("[data-km-nenhum]");
  if (!itens.length) {
    if (nenhum instanceof HTMLElement) nenhum.hidden = false;
    return;
  }
  const linhas = itens.map(descrever);
  const lista = raiz.querySelector("[data-km-lista]");
  for (const texto of linhas) {
    const item = document.createElement("li");
    item.textContent = texto;
    lista?.append(item);
  }
  const texto = ["Diário de bordo: km anotados no aparelho e não enviados (link vencido)",
                 ...linhas].join("\n");
  const area = raiz.querySelector("[data-km-texto]");
  if (area instanceof HTMLTextAreaElement) area.value = texto;
  if (bloco instanceof HTMLElement) bloco.hidden = false;

  const aviso = raiz.querySelector("[data-km-copiado]");
  raiz.querySelector("[data-km-copiar]")?.addEventListener("click", async () => {
    let copiou = false;
    try {
      await navigator.clipboard.writeText(texto);
      copiou = true;
    } catch {
      // Sem a API da área de transferência: seleciona o texto para copiar pelo aparelho.
      if (area instanceof HTMLTextAreaElement) {
        area.focus();
        area.select();
      }
    }
    if (aviso) {
      aviso.textContent = copiou
        ? "Copiado. Cole na conversa com o setor de viagens."
        : "O texto está selecionado: copie pelo menu do aparelho.";
    }
  });
}

/** @param {string} prefixo @returns {Pendente[]} */
function pendentes(prefixo) {
  /** @type {Pendente[]} */
  const itens = [];
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const chave = window.localStorage.key(i);
      if (!chave || !chave.startsWith(prefixo)) continue;
      try {
        const item = JSON.parse(window.localStorage.getItem(chave) || "null");
        if (item && typeof item === "object") itens.push(/** @type {Pendente} */ (item));
      } catch {
        // Um item ilegível não impede os outros.
      }
    }
  } catch {
    // Sem armazenamento (navegação privada): não há o que mostrar.
  }
  return itens.sort((a, b) => (a.linha || 0) - (b.linha || 0));
}

/** @param {number | null | undefined} valor */
function km(valor) {
  return valor === null || valor === undefined ? "—" : valor.toLocaleString("pt-BR");
}

/** @param {Pendente} item @returns {string} */
function descrever(item) {
  const campos = item.campos || {};
  const partes = [];
  if ("km_inicial" in campos) partes.push(`saída ${km(campos.km_inicial)} km`);
  if ("km_final" in campos) partes.push(`chegada ${km(campos.km_final)} km`);
  const quando = item.digitado_em ? new Date(item.digitado_em) : null;
  const anotado = quando && !Number.isNaN(quando.getTime())
    ? ` (anotado em ${quando.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })})`
    : "";
  const situacao = item.estado === "conflito" ? ", diferente do que está no sistema"
    : item.estado === "recusado" ? ", recusado pelo sistema" : "";
  const nome = item.rotulo || `Trecho ${item.chave || item.linha || "?"}`;
  return `${nome}: ${partes.join(", ") || "sem km"}${anotado}${situacao}.`;
}

export {};
