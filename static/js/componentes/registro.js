// @ts-check
/**
 * Listas de registros: o resumo em janela, o destaque de quem acabou de ser salvo e a
 * continuidade da placa ao abrir um registro.
 *
 * O resumo é pedido por HTMX (o próprio <a> do registro) e cai dentro de #resumo-dialogo;
 * aqui ficam o esqueleto a cada abertura, o estado de carregando e a mensagem de erro.
 */
// Continuidade espacial com custo mínimo: ao sair da página por um registro, só a placa
// daquele registro mantém o nome de transição (as outras 19 não viram snapshot).
/** @type {Element | null} */
let registroAtivado = null;
document.addEventListener("click", (e) => {
  registroAtivado = /** @type {HTMLElement} */ (e.target).closest(".registro");
}, true);
window.addEventListener("pageswap", (evento) => {
  if (!(/** @type {any} */ (evento)).viewTransition) return;
  document.querySelectorAll(".registro .placa[data-vt]").forEach((placa) => {
    if (!registroAtivado || !registroAtivado.contains(placa)) placa.removeAttribute("data-vt");
  });
});

// Recém-alterado: a linha do registro que acabou de ser salvo acende em dourado — a pessoa
// volta da edição e sabe onde o item está sem procurar.
try {
  const chave = window.sessionStorage.getItem("pcpr-destaque");
  const alvo = chave ? document.querySelector(`.registro[data-destaque="${CSS.escape(chave)}"]`) : null;
  if (chave) window.sessionStorage.removeItem("pcpr-destaque");
  if (alvo) {
    alvo.classList.add("registro--destaque");
    alvo.addEventListener("animationend", () => alvo.classList.remove("registro--destaque"), { once: true });
    const r = alvo.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) alvo.scrollIntoView({ block: "center" });
  }
} catch {
  /* sessionStorage bloqueado: sem destaque */
}

const ESQUELETO = `<div class="dialogo__corpo" aria-busy="true">
  <p class="sr-only" role="status">Carregando o resumo do ofício.</p>
  <div class="esqueleto esqueleto--linha"></div>
  <div class="esqueleto esqueleto--linha"></div>
  <div class="esqueleto esqueleto--curto"></div>
</div>`;

/**
 * Corpo da janela que este pedido vai preencher — serve ao resumo do ofício e à lista de
 * ofícios de um roteiro. @param {Event} evento
 */
function corpoDaJanela(evento) {
  const origem = /** @type {HTMLElement | undefined} */ (
    /** @type {CustomEvent} */ (evento).detail?.elt
  );
  const id = origem?.getAttribute("data-abrir-dialogo");
  if (!id) return null;
  return document.getElementById(id)?.querySelector("[data-corpo-dialogo]") ?? null;
}

// Cada abertura começa do esqueleto: o conteúdo do item anterior não pode ficar na tela
// enquanto o novo não chega.
document.body.addEventListener("htmx:beforeRequest", (evento) => {
  const corpo = corpoDaJanela(evento);
  if (corpo) corpo.innerHTML = ESQUELETO;
});

// Chegou de outra tela pedindo um ofício ("?resumo=<pk>"): a janela já veio desenhada,
// então é só abrir — e o endereço perde o parâmetro, para recarregar não reabri-la.
const janelaPedida = /** @type {HTMLDialogElement | null} */ (
  document.querySelector("dialog[data-abrir-ao-carregar]")
);
if (janelaPedida) {
  janelaPedida.showModal();
  const url = new URL(window.location.href);
  url.searchParams.delete("resumo");
  window.history.replaceState(null, "", url);
}

// Enquanto a próxima página não chega, o item clicado mostra que está a caminho.
document.addEventListener("click", (evento) => {
  const item = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest(".lista-ligacoes__item")
  );
  if (item && !evento.defaultPrevented) item.setAttribute("aria-busy", "true");
});
window.addEventListener("pageshow", () => {
  document.querySelectorAll(".lista-ligacoes__item[aria-busy]").forEach(
    (e) => e.removeAttribute("aria-busy"));
});

document.body.addEventListener("htmx:responseError", (evento) => {
  const corpo = corpoDaJanela(evento);
  if (!corpo) return;
  corpo.innerHTML = "";
  const aviso = document.createElement("p");
  aviso.className = "dialogo__corpo registro__erro";
  aviso.setAttribute("role", "alert");
  aviso.textContent = "Não foi possível carregar agora. Feche e tente de novo.";
  corpo.append(aviso);
});

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
