// @ts-check
/**
 * Folha do termo: vincular ofícios preenche os campos com os dados deles, unidos.
 *
 * Como "usar um roteiro" na folha do ofício: escolher um ofício na busca traz destinos,
 * período, equipe e viatura (de todos os vinculados) para os campos do termo — valores de verdade, que a pessoa vê e
 * ajusta — em vez de deixar os campos vazios "herdando" do ofício. Os dados vêm de
 * viagens:dados_do_oficio_para_termo (`data-dados-oficio` no <form>).
 *
 * Os campos recebem `input`/`change`, então o autosave grava como se a pessoa tivesse
 * digitado.
 */

const form = /** @type {HTMLFormElement | null} */ (document.getElementById("form-termo"));
const url = form?.dataset.dadosOficio || "";

/** @param {Element | null} el */
function avisar(el) {
  el?.dispatchEvent(new Event("input", { bubbles: true }));
  el?.dispatchEvent(new Event("change", { bubbles: true }));
}

/** @param {{cidade: string, uf: string}[]} destinos */
function preencherDestinos(destinos) {
  const comp = /** @type {any} */ (document.querySelector("pc-destinos"));
  if (!comp || !destinos.length) return;
  const linhas = () => /** @type {HTMLElement[]} */ (Array.from(comp.querySelectorAll("[data-destino]")));
  while (linhas().length < destinos.length) comp.adicionar();
  while (linhas().length > destinos.length) linhas().at(-1)?.remove();
  linhas().forEach((linha, i) => {
    const uf = /** @type {HTMLSelectElement | null} */ (linha.querySelector("[data-uf]"));
    if (uf) { uf.value = destinos[i].uf; comp.filtrar(uf); }
    const cidade = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[role='combobox']"));
    const valor = /** @type {HTMLInputElement | null} */ (linha.querySelector("input[data-valor-id]"));
    if (cidade) cidade.value = destinos[i].cidade;
    if (valor) { valor.value = destinos[i].cidade; avisar(valor); }
  });
  comp.renumerar();
}

/** @param {string} inicio @param {string} fim */
function preencherPeriodo(inicio, fim) {
  const de = /** @type {HTMLInputElement | null} */ (document.querySelector("[data-periodo-de]"));
  const ate = /** @type {HTMLInputElement | null} */ (document.querySelector("[data-periodo-ate]"));
  const visivel = /** @type {HTMLInputElement | null} */ (document.getElementById("termo-periodo"));
  if (!de || !inicio) return;
  de.value = inicio;
  if (ate) ate.value = fim;
  if (visivel) visivel.value = fim ? `${inicio} a ${fim}` : inicio;
  avisar(de);
}

/** @param {{id: string, titulo: string, meta?: string}[]} servidores */
function preencherEquipe(servidores) {
  const multi = /** @type {any} */ (document.querySelector("pc-multiescolha[data-nome='servidores']"));
  if (!multi || !servidores.length) return;
  multi.querySelectorAll(".multiescolha__item").forEach((/** @type {Element} */ i) => i.remove());
  servidores.forEach((s) => multi.adicionar(s));
  multi.sincronizar?.();
  avisar(multi);
}

/** @param {string} viatura */
function preencherViatura(viatura) {
  const select = /** @type {HTMLSelectElement | null} */ (document.querySelector("select[name='viatura']"));
  if (!select || !viatura) return;
  select.value = viatura;
  avisar(select);
}

// Um ofício a mais nos vinculados: os campos recebem a união de todos (destinos de todos,
// da primeira saída à última chegada, a equipe toda, a primeira viatura).
document.addEventListener("pc-escolhido", async (evento) => {
  const origem = /** @type {HTMLElement} */ (evento.target);
  const campo = origem.closest("[data-oficio-do-termo]");
  if (!url || !campo) return;
  const opcao = /** @type {CustomEvent} */ (evento).detail;
  const ids = Array.from(campo.querySelectorAll("input[type='hidden'][name='oficios']"),
    (i) => /** @type {HTMLInputElement} */ (i).value).filter(Boolean);
  if (!ids.length) return;
  const endereco = `${url.replace("/0/", `/${encodeURIComponent(ids[0])}/`)}?oficios=${ids.join(",")}`;
  const resposta = await fetch(endereco,
    { credentials: "same-origin", headers: { Accept: "application/json" } }).catch(() => null);
  if (!resposta?.ok) return;
  const dados = await resposta.json();
  preencherDestinos(dados.destinos || []);
  preencherPeriodo(dados.inicio || "", dados.fim || "");
  preencherEquipe(dados.servidores || []);
  preencherViatura(dados.viatura || "");
  const mensagem = ids.length > 1
    ? `Dados dos ${ids.length} ofícios unidos nos campos. Confira e ajuste o que precisar.`
    : `Dados do ${opcao?.titulo || "ofício"} preenchidos. Confira e ajuste o que precisar.`;
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel: "info" } }));
});



// ------------------------------------------------------------------ trocar o documento
// Escolher outro documento na lista troca só a lista e o visualizador "Como vai sair" —
// sem recarregar a página (que piscava e pulava de lugar). Texto editado e ainda não
// salvo no editor é gravado antes da troca. Sem JS, o link continua levando à página.
document.addEventListener("click", async (evento) => {
  const link = /** @type {HTMLAnchorElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("a[data-trocar-previa]"));
  if (!link || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) return;
  evento.preventDefault();
  if (link.getAttribute("aria-current") === "true") return;
  const editor = /** @type {any} */ (document.querySelector("#previa pc-editor-documento"));
  if (editor?.sujo && typeof editor.salvar === "function") await editor.salvar();
  const url = new URL(link.href, window.location.href);
  url.hash = "";
  try {
    const resposta = await fetch(url, { headers: { Accept: "text/html" } });
    if (!resposta.ok) throw new Error(String(resposta.status));
    const nova = new DOMParser().parseFromString(await resposta.text(), "text/html");
    for (const id of ["lista-documentos", "previa"]) {
      const atual = document.getElementById(id);
      const substituta = nova.getElementById(id);
      if (atual && substituta) atual.replaceWith(document.importNode(substituta, true));
    }
    window.history.replaceState(window.history.state, "", url.pathname + url.search + "#previa");
    /** @type {HTMLElement | null} */ (document.querySelector("#lista-documentos [aria-current='true']"))
      ?.focus({ preventScroll: true });
  } catch {
    window.location.href = link.href;  // sem rede ou erro: a navegação comum
  }
});

export {};
