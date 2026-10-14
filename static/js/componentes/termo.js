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

// Quem vai em cada viatura (termos/editar.html): o seletor segmentado de cada servidor é
// um grupo de rádios `viatura_do_<id>` — a gravação automática guarda a troca. Aqui só o
// realce que desliza até a opção marcada e a conta de cada viatura, que muda na hora (o
// bloco só é redesenhado quando o foco sai dele).
/** @param {HTMLElement} escala @param {boolean} animar */
function posicionarRealce(escala, animar) {
  const marcado = /** @type {HTMLInputElement | null} */ (escala.querySelector("input:checked"));
  const rotulo = /** @type {HTMLElement | null} */ (marcado?.nextElementSibling ?? null);
  if (!rotulo || !rotulo.offsetWidth) return;
  escala.classList.toggle("escala--parada", !animar);
  escala.style.setProperty("--escala-x", `${rotulo.offsetLeft}px`);
  escala.style.setProperty("--escala-w", `${rotulo.offsetWidth}px`);
  escala.classList.add("escala--viva");
  if (!animar) requestAnimationFrame(() => escala.classList.remove("escala--parada"));
}

function prepararEscalas() {
  document.querySelectorAll("[data-escala]").forEach((e) => posicionarRealce(/** @type {HTMLElement} */ (e), false));
}

function recontarFrota() {
  document.querySelectorAll("[data-frota-conta]").forEach((conta) => {
    const id = /** @type {HTMLElement} */ (conta).dataset.frotaConta || "";
    const n = String(document.querySelectorAll(`[data-escala] input[value="${CSS.escape(id)}"]:checked`).length);
    if (conta.textContent === n) return;
    conta.textContent = n;
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
  recontarFrota();
});
prepararEscalas();
document.fonts?.ready.then(prepararEscalas);
window.addEventListener("resize", prepararEscalas);
document.addEventListener("pcpr:pagina-refeita", () => requestAnimationFrame(prepararEscalas));

// Data do evento: clicar nas folhas do calendário é o mesmo que o botão do calendário.
document.addEventListener("click", (evento) => {
  const folhas = /** @type {HTMLElement} */ (evento.target).closest?.("[data-abre-calendario]");
  if (!folhas) return;
  const botao = /** @type {HTMLButtonElement | null} */ (
    folhas.closest(".mesa-evento")?.querySelector(".mesa-evento__botao") ?? null);
  if (botao && !botao.disabled && botao.getAttribute("aria-expanded") !== "true") botao.click();
});

export {};
