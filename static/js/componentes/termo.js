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
  // O componente tem um teto de destinos (data-maximo): os que passam dele ficam de fora,
  // e o laço para quando "adicionar" não acrescenta mais (sem isso a aba travava).
  const maximo = Number(comp.dataset?.maximo || 0);
  if (maximo && destinos.length > maximo) {
    destinos = destinos.slice(0, maximo);
    document.body.dispatchEvent(new CustomEvent("toast", { detail: {
      mensagem: `Os ofícios somam mais de ${maximo} destinos: entraram os ${maximo} primeiros.`,
      nivel: "aviso" } }));
  }
  while (linhas().length < destinos.length) {
    const antes = linhas().length;
    comp.adicionar();
    if (linhas().length === antes) break;
  }
  while (linhas().length > destinos.length) linhas().at(-1)?.remove();
  destinos = destinos.slice(0, linhas().length);
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
  const visivel = /** @type {HTMLInputElement | null} */ (document.getElementById("termo-periodo"));  // escondido: o calendário lê dele
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

// Um ofício a mais nos vinculados: os campos recebem a união de todos (destinos de todos,
// da primeira saída à última chegada, a equipe toda). As viaturas vêm pelo servidor: cada
// ofício que entra traz a sua, com a equipe dele (termos.salvar), e o bloco se redesenha.
let pedidoAtual = 0;  // só a resposta do último ofício escolhido preenche os campos

document.addEventListener("pc-escolhido", async (evento) => {
  const origem = /** @type {HTMLElement} */ (evento.target);
  const campo = origem.closest("[data-oficio-do-termo]");
  if (!url || !campo) return;
  const opcao = /** @type {CustomEvent} */ (evento).detail;
  const ids = Array.from(campo.querySelectorAll("input[type='hidden'][name='oficios']"),
    (i) => /** @type {HTMLInputElement} */ (i).value).filter(Boolean);
  if (!ids.length) return;
  const este = ++pedidoAtual;
  const endereco = `${url.replace("/0/", `/${encodeURIComponent(ids[0])}/`)}?oficios=${ids.join(",")}`;
  const resposta = await fetch(endereco,
    { credentials: "same-origin", headers: { Accept: "application/json" } }).catch(() => null);
  if (!resposta?.ok || este !== pedidoAtual) return;
  const dados = await resposta.json().catch(() => null);
  if (!dados || este !== pedidoAtual) return;
  preencherDestinos(dados.destinos || []);
  preencherPeriodo(dados.inicio || "", dados.fim || "");
  preencherEquipe(dados.servidores || []);
  const mensagem = ids.length > 1
    ? `Dados dos ${ids.length} ofícios unidos nos campos. Confira e ajuste o que precisar.`
    : `Dados do ${opcao?.titulo || "ofício"} preenchidos. Confira e ajuste o que precisar.`;
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel: "info" } }));
});


// Transporte: tirar ou acrescentar uma viatura muda os cartões — o foco sai do controle
// para que a gravação automática possa redesenhar o bloco (autosave.js não troca a região
// que está em uso).
document.addEventListener("change", (evento) => {
  const alvo = /** @type {HTMLElement} */ (evento.target);
  if (!alvo.closest?.("#transporte")) return;
  if (alvo.matches("[data-remover-viatura], select[name='adicionar_viatura']")) {
    /** @type {HTMLElement | null} */ (document.activeElement)?.blur?.();
  }
});

// Quem vai em cada viatura (termos/editar.html): com mais de uma viatura, cada cartão da
// equipe ganha um selo com a placa (ou "Escolha a viatura") e, embaixo, um seletor
// segmentado — rádios `viatura_do_<id>` que a gravação automática guarda — que só desce
// com o mouse ou o foco no cartão (CSS). As opções e a escolha de cada um vêm de
// #transporte (`data-opcoes`, `data-lotacao`), que se refaz depois de gravar; o que a
// pessoa marcou na tela vence o que veio do servidor.

/** @returns {{opcoes: {pk: string, placa: string}[], lotacao: Record<string, string>}} */
function lerTransporte() {
  const bloco = /** @type {HTMLElement | null} */ (document.getElementById("transporte"));
  try {
    return { opcoes: JSON.parse(bloco?.dataset.opcoes || "[]"),
             lotacao: JSON.parse(bloco?.dataset.lotacao || "{}") };
  } catch {
    return { opcoes: [], lotacao: {} };
  }
}

/** Ícone do sprite (o mesmo arquivo dos ícones da página). @param {string} nome */
function icone(nome) {
  const uso = document.querySelector("svg.icone use")?.getAttribute("href") || "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icone icone--sm");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `${uso.split("#")[0]}#i-${nome}`);
  svg.append(use);
  return svg;
}

/** O selo do cartão: a placa escolhida, ou o aviso. @param {HTMLElement} cartao */
function atualizarSelo(cartao) {
  const selo = cartao.querySelector("[data-lotacao-selo]");
  if (!selo) return;
  const marcado = /** @type {HTMLInputElement | null} */ (cartao.querySelector("[data-escala] input:checked"));
  const placa = marcado?.nextElementSibling?.textContent || "";
  selo.replaceChildren(icone(placa ? "check" : "alert-circle"),
    document.createTextNode(placa || "Escolha a viatura"));
  selo.classList.toggle("lotacao-selo--falta", !placa);
}

/** @param {HTMLElement} escala @param {boolean} animar */
function posicionarRealce(escala, animar) {
  const marcado = /** @type {HTMLInputElement | null} */ (escala.querySelector("input:checked"));
  const rotulo = /** @type {HTMLElement | null} */ (marcado?.nextElementSibling ?? null);
  if (!rotulo || !rotulo.offsetWidth) {
    escala.classList.remove("escala--viva");
    return;
  }
  escala.classList.toggle("escala--parada", !animar);
  escala.style.setProperty("--escala-x", `${rotulo.offsetLeft}px`);
  escala.style.setProperty("--escala-w", `${rotulo.offsetWidth}px`);
  escala.classList.add("escala--viva");
  if (!animar) requestAnimationFrame(() => escala.classList.remove("escala--parada"));
}

function prepararEscalas() {
  document.querySelectorAll("[data-escala]").forEach((e) => posicionarRealce(/** @type {HTMLElement} */ (e), false));
}

function decorarEquipe() {
  const { opcoes, lotacao } = lerTransporte();
  const chave = opcoes.map((o) => o.pk).join(",");
  document.querySelectorAll("#form-termo .equipe__cartao[data-servidor]").forEach((no) => {
    const cartao = /** @type {HTMLElement} */ (no);
    const id = cartao.dataset.servidor || "";
    const atual = /** @type {HTMLElement | null} */ (cartao.querySelector(".lotacao-gaveta"));
    if (atual && atual.dataset.opcoes === chave) return;
    const antes = /** @type {HTMLInputElement | null} */ (atual?.querySelector("input:checked"))?.value;
    atual?.remove();
    cartao.querySelector("[data-lotacao-selo]")?.remove();
    cartao.classList.toggle("equipe__cartao--lotacao", opcoes.length > 1);
    if (opcoes.length < 2) return;
    const escolhida = antes ?? lotacao[id] ?? "";
    const nome = cartao.dataset.nome || "";

    const selo = document.createElement("span");
    selo.className = "lotacao-selo";
    selo.dataset.lotacaoSelo = "";
    cartao.querySelector(".pessoa__texto")?.after(selo);

    const gaveta = document.createElement("div");
    gaveta.className = "lotacao-gaveta";
    gaveta.dataset.opcoes = chave;
    const escala = document.createElement("span");
    escala.className = "escala lotacao-gaveta__escala";
    escala.dataset.escala = "";
    escala.setAttribute("role", "radiogroup");
    escala.setAttribute("aria-label", `Viatura de ${nome}`);
    const realce = document.createElement("span");
    realce.className = "escala__realce";
    realce.setAttribute("aria-hidden", "true");
    escala.append(realce);
    for (const o of opcoes) {
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = `viatura_do_${id}`;
      radio.id = `vd-${id}-${o.pk}`;
      radio.value = o.pk;
      radio.checked = o.pk === escolhida;
      const rotulo = document.createElement("label");
      rotulo.htmlFor = radio.id;
      rotulo.textContent = o.placa;
      escala.append(radio, rotulo);
    }
    const dentro = document.createElement("div");
    dentro.className = "lotacao-gaveta__dentro";
    dentro.append(escala);
    gaveta.append(dentro);
    cartao.append(gaveta);
    atualizarSelo(cartao);
    posicionarRealce(escala, false);
  });
}

/** Quantos vão em cada viatura, na hora (o bloco só se refaz depois de gravar). */
function recontarFrota() {
  document.querySelectorAll("[data-frota-conta]").forEach((conta) => {
    const id = /** @type {HTMLElement} */ (conta).dataset.frotaConta || "";
    const n = document.querySelectorAll(`[data-escala] input[value="${CSS.escape(id)}"]:checked`).length;
    const texto = `${n} ${n === 1 ? "servidor" : "servidores"}`;
    if (conta.textContent === texto) return;
    conta.textContent = texto;
    conta.classList.remove("frota__conta--mudou");
    void (/** @type {HTMLElement} */ (conta)).offsetWidth; // reinicia o pulo
    conta.classList.add("frota__conta--mudou");
  });
}

document.addEventListener("change", (evento) => {
  const alvo = /** @type {HTMLElement} */ (evento.target);
  const escala = /** @type {HTMLElement | null} */ (alvo.closest?.("[data-escala]") ?? null);
  if (!escala) return;
  posicionarRealce(escala, true);
  const cartao = /** @type {HTMLElement | null} */ (escala.closest(".equipe__cartao"));
  if (cartao) atualizarSelo(cartao);
  recontarFrota();
});
// A gaveta desce ao passar o mouse: o realce é medido quando ela fica visível.
document.addEventListener("pointerover", (evento) => {
  const cartao = /** @type {HTMLElement} */ (evento.target).closest?.(".equipe__cartao--lotacao");
  const escala = /** @type {HTMLElement | null} */ (cartao?.querySelector("[data-escala]") ?? null);
  if (escala && !escala.classList.contains("escala--viva")) posicionarRealce(escala, false);
});
// Pessoa nova na equipe (o cartão nasce no cliente) e bloco refeito depois de gravar.
const listaEquipe = document.querySelector("#form-termo .equipe__cartoes");
if (listaEquipe) new MutationObserver(() => decorarEquipe()).observe(listaEquipe, { childList: true });
decorarEquipe();
document.fonts?.ready.then(prepararEscalas);
window.addEventListener("resize", prepararEscalas);
document.addEventListener("pcpr:pagina-refeita", () => requestAnimationFrame(() => {
  decorarEquipe();
  prepararEscalas();
}));

export {};
