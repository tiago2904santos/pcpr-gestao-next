// @ts-check
/**
 * Ponto de entrada do front-end. Sem bundler: módulos ES servidos direto.
 * O que toda tela usa (shell, menus, diálogos, toasts, paleta, ações HTMX) entra sempre, pré-carregado
 * com <link rel="modulepreload"> (templates/base_documento.html). O resto só entra quando a tela tem
 * o elemento que o pede — a tela que precisa pré-carrega os seus no bloco `modulos`.
 */
import "./componentes/shell.js";
import "./componentes/menu.js";
import "./componentes/dialogo.js";
import "./componentes/toasts.js";
import "./componentes/comandos.js";
import "./componentes/acao.js";

/** @type {Array<[string, () => Promise<unknown>]>} */
const sobDemanda = [
  ["[data-copiar-alvo]", () => import("./componentes/copiar.js")],
  ["#conferencia, .prontidao-documental", () => import("./componentes/conferencia.js")],
  ["pc-combobox", () => import("./componentes/combobox.js")],
  ["pc-abas", () => import("./componentes/abas.js")],
  [".abas, [data-rola-lado]", () => import("./componentes/abas-rolagem.js")],
  [".filtros__mais, [data-erro-lista]", () => import("./componentes/filtros.js")],
  ["[data-mascara]", () => import("./componentes/mascara.js")],
  ["a.voltar-tarefa", () => import("./componentes/voltar-na-barra.js")],
  [".barra-acoes--registro, .barra-acoes--colecao", () => import("./componentes/barra-grudada.js")],
  ["input[type='search'].entrada, input[data-limpavel]", () => import("./componentes/limpar.js")],
  ["form[data-proteger]", () => import("./componentes/protecao.js")],
  ["form[data-autosave]", () => import("./componentes/autosave.js")],
  [".registro", () => import("./componentes/registro.js")],
  [".documento:has(.secao__numero), .documento--cartoes", () => import("./componentes/guia.js")],
  [".progresso, [data-indice-preparacao]", () => import("./componentes/progresso.js")],
  ["pc-data", () => import("./componentes/seletor-data.js")],
  ["pc-hora", () => import("./componentes/seletor-hora.js")],
  ["pc-select", () => import("./componentes/seletor.js")],
  ["pc-escolhas", () => import("./componentes/escolhas.js")],
  ["pc-transporte", () => import("./componentes/transporte.js")],
  ["[data-texto-pronto]", () => import("./componentes/texto-pronto.js")],
  ["pc-multiescolha", () => import("./componentes/multiescolha.js")],
  [".passos", () => import("./componentes/passos.js")],
  // Ofícios vinculados: pergunta se os da mesma ação (roteiro, viagem) entram também.
  ["pc-multiescolha[data-variante='oficios']", () => import("./componentes/oficios-irmaos.js")],
  ["pc-destinos", () => import("./componentes/destinos.js")],
  ["form#form-termo", () => import("./componentes/termo.js")],
  ["pc-linhas", () => import("./componentes/linhas.js")],
  ["[data-esvaziar]", () => import("./componentes/esvaziar.js")],
  ["#dialogo-assinado", () => import("./componentes/assinado.js")],
  ["[data-baixar-arquivo]", () => import("./componentes/baixar-arquivo.js")],
  ["[data-conjuntos]", () => import("./componentes/conjuntos.js")],
  ["[data-diaria-base]", () => import("./componentes/diaria.js")],
  ["[data-sugerir], [data-copiar-de]", () => import("./componentes/sugerir.js")],
];
const carregados = new Set();
/** @type {{botao: HTMLElement, cancelada: boolean} | null} */
let aberturaBaixar = null;
document.addEventListener("click", async (evento) => {
  const botao = evento.target instanceof Element ? evento.target.closest("[data-baixar-documentos]") : null;
  if (!(botao instanceof HTMLElement) || botao.getAttribute("aria-disabled") === "true"
      || !document.getElementById("dialogo-baixar")) return;
  evento.preventDefault();
  if (aberturaBaixar && !aberturaBaixar.cancelada) return;
  const pedido = { botao, cancelada: false };
  aberturaBaixar = pedido;
  botao.setAttribute("aria-busy", "true");
  const foco = document.activeElement;
  try {
    const modulo = await import("./componentes/baixar.js");
    if (pedido.cancelada || !botao.isConnected) return;
    const aberta = modulo.abrirDialogo(botao);
    // A janela já abriu: o GET pertence a ela, e fechar/reabrir pode tentar outra leitura.
    if (aberturaBaixar === pedido) {
      aberturaBaixar = null;
      botao.removeAttribute("aria-busy");
    }
    await aberta;
  } catch (erro) {
    if (pedido.cancelada || !botao.isConnected) return;
    document.body.dispatchEvent(new CustomEvent("toast", { detail: {
      nivel: "perigo", mensagem: "Não foi possível abrir os documentos. Recarregue a página e tente de novo.",
    } }));
    if (document.activeElement === foco || document.activeElement === document.body) {
      const origem = botao.closest("pc-menu")?.querySelector("[data-menu-botao]") || botao;
      if (origem instanceof HTMLElement) origem.focus({ preventScroll: true });
    }
    console.error("Não foi possível carregar a janela de documentos.", erro);
  } finally {
    if (aberturaBaixar === pedido) {
      aberturaBaixar = null;
      botao.removeAttribute("aria-busy");
    }
  }
});
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape" && aberturaBaixar && !document.querySelector("#dialogo-baixar[open]")) {
    aberturaBaixar.cancelada = true;
    aberturaBaixar.botao.removeAttribute("aria-busy");
  }
});
/** @type {HTMLElement | null} */
let focoAdiado = null;
/** @param {Element} alvo */
function disponivel(alvo) {
  if (!alvo.closest("[data-controladores-adiados]")) return true;
  // No navegador testado, a geometria sozinha não excluiu controles de details fechado.
  // O summary e a própria raiz continuam disponíveis (abrir a gaveta é carga inicial).
  for (let no = alvo.parentElement; no; no = no.parentElement) {
    if (no instanceof HTMLDetailsElement && !no.open
        && !no.querySelector(":scope > summary")?.contains(alvo)) return false;
  }
  return alvo.getClientRects().length > 0 && getComputedStyle(alvo).visibility !== "hidden";
}
function preservarFocoAdiado() {
  // Registrar um seletor pode ocultar o select nativo que recebeu Tab durante o import.
  const campo = focoAdiado;
  if (!campo?.isConnected || !campo.hidden || document.activeElement !== document.body) return;
  const componente = campo.closest("pc-select, pc-combobox, pc-multiescolha");
  const substituto = /** @type {HTMLElement | undefined} */ (
    Array.from(componente?.querySelectorAll("button[role='combobox'], input:not([type='hidden'])") || [])
      .find((alvo) => alvo.getClientRects().length > 0));
  substituto?.focus({ preventScroll: true });
}
function carregarSobDemanda() {
  for (const [seletor, carregar] of sobDemanda) {
    if (carregados.has(seletor)
        || !Array.from(document.querySelectorAll(seletor)).some(disponivel)) continue;
    carregados.add(seletor);
    carregar().then(preservarFocoAdiado).catch((erro) => {
      carregados.delete(seletor);
      console.error("Não foi possível carregar os controles da página.", erro);
    });
  }
}
carregarSobDemanda();
// Fragmentos HTMX podem trazer um componente que a tela ainda não tinha.
document.body.addEventListener("htmx:afterSwap", carregarSobDemanda);
// Opt-in: abrir/focar uma gaveta ou diálogo torna seus controles disponíveis.
document.addEventListener("toggle", (evento) => {
  if (evento.target instanceof Element && evento.target.matches("[data-controladores-adiados]")) {
    carregarSobDemanda();
  }
}, true);
document.addEventListener("focusin", (evento) => {
  const alvo = evento.target;
  focoAdiado = alvo instanceof HTMLElement && alvo.closest("[data-controladores-adiados]")
    ? alvo : null;
  if (focoAdiado) carregarSobDemanda();
});
document.addEventListener("pcpr:controladores-repostos", carregarSobDemanda);

/**
 * Componentes pesados que ficam longe do topo só carregam quando chegam perto da tela
 * (ex.: o editor de documento, 39 KB, no fim da folha do ofício). Sem IntersectionObserver,
 * carregam na hora.
 * @type {Array<[string, (alvo: Element) => Promise<unknown>]>}
 */
const quandoVisivel = [
  ["[data-editores]", async (alvo) => {
    const { iniciarBloco } = await import("./componentes/editores.js");
    if (alvo instanceof HTMLElement && alvo.isConnected) iniciarBloco(alvo);
  }],
  ["pc-editor-documento", () => import("./componentes/editor-documento.js")],
  ["pc-editor-documento[data-editavel]", () => import("./componentes/entidades-documento.js")],
];
/** @type {Map<string, WeakSet<Element>>} */
const iniciadosVisiveis = new Map();
/** @type {Map<string, IntersectionObserver>} */
const observadoresVisiveis = new Map();
/** @param {Event} [evento] */
function carregarQuandoVisivel(evento) {
  for (const [seletor, carregar] of quandoVisivel) {
    // Desliga caixas removidas e observa os alvos atuais, inclusive HTMX antes do import.
    observadoresVisiveis.get(seletor)?.disconnect();
    const iniciados = iniciadosVisiveis.get(seletor) || new WeakSet();
    iniciadosVisiveis.set(seletor, iniciados);
    const alvos = new Set(Array.from(document.querySelectorAll(seletor),
      (alvo) => alvo.closest("[data-editores]") || alvo));
    const trocado = /** @type {CustomEvent | undefined} */ (evento)?.detail?.target || evento?.target;
    if (evento?.type === "htmx:afterSwap" && trocado instanceof Element) {
      alvos.forEach((alvo) => {
        if (trocado.contains(alvo) || alvo.contains(trocado)) iniciados.delete(alvo);
      });
    }
    const carregarAlvo = (/** @type {Element} */ alvo) => {
      if (!alvo.isConnected || iniciados.has(alvo)) return;
      iniciados.add(alvo);
      carregar(alvo).catch((erro) => {
        iniciados.delete(alvo);  // próximo swap pode tentar novamente se o import falhou
        console.error("Não foi possível carregar o editor do documento.", erro);
      });
    };
    if (!("IntersectionObserver" in window)) { alvos.forEach(carregarAlvo); continue; }
    const observador = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (!entrada.isIntersecting) continue;
        observador.unobserve(entrada.target);
        carregarAlvo(entrada.target);
      }
    }, { rootMargin: "400px 0px" });
    observadoresVisiveis.set(seletor, observador);
    // Num bloco de vários editores (o termo), o editor não tem caixa própria
    // (display: contents) e nunca "apareceria": observa-se o bloco.
    alvos.forEach((alvo) => { if (!iniciados.has(alvo)) observador.observe(alvo); });
  }
}
carregarQuandoVisivel();
document.body.addEventListener("htmx:afterSwap", carregarQuandoVisivel);
document.addEventListener("pcpr:editores-repostos", carregarQuandoVisivel);

// Com JavaScript, o que só serve sem ele some (ex.: "Aplicar" numa busca que já é ao vivo).
document.querySelectorAll("[data-so-sem-js]").forEach((e) => { /** @type {HTMLElement} */ (e).hidden = true; });

// Campo de senha: mostrar/ocultar (componentes/campo_senha.html).
document.querySelectorAll("[data-alternar-senha]").forEach((b) => b.removeAttribute("hidden"));
document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (evento.target).closest("[data-alternar-senha]")
  );
  if (!botao) return;
  const campo = /** @type {HTMLInputElement | null} */ (
    document.getElementById(botao.getAttribute("aria-controls") || "")
  );
  if (!campo) return;
  const mostrar = campo.type === "password";
  campo.type = mostrar ? "text" : "password";
  botao.setAttribute("aria-pressed", String(mostrar));
  const rotulo = botao.querySelector(".sr-only");
  if (rotulo) rotulo.textContent = mostrar ? "Ocultar senha" : "Mostrar senha";
  campo.focus({ preventScroll: true });
});

// Ao salvar um registro, a lista de onde se veio acende a linha dele (registro.js).
document.addEventListener("submit", (evento) => {
  const form = /** @type {HTMLFormElement} */ (evento.target);
  const chave = form.dataset.destaque;
  if (!chave || evento.defaultPrevented) return;
  try {
    window.sessionStorage.setItem("pcpr-destaque", chave);
  } catch {
    /* armazenamento indisponível: só não há destaque */
  }
});

// Sessão expirada em qualquer pedido assíncrono (fetch dos componentes, HTMX): o servidor
// responde 401 com `X-Sessao-Expirada` e o caminho de volta (identidade/middleware.py). Aqui a
// página avisa uma vez, com o link "Entrar de novo" — cada componente continua tratando a
// falha do seu jeito (o menu ⋮ diz no próprio menu). O HTMX ainda recarrega no login pelo
// `HX-Redirect`.
const fetchOriginal = window.fetch.bind(window);
window.fetch = async (...args) => {
  const resposta = await fetchOriginal(...args);
  if (resposta.status === 401 && resposta.headers.get("X-Sessao-Expirada")) {
    const corpo = await resposta.clone().json().catch(() => ({}));
    document.dispatchEvent(new CustomEvent("pcpr:sessao-expirada", { detail: corpo }));
  }
  return resposta;
};

// HTMX: envia o token CSRF em toda requisição e respeita prefers-reduced-motion.
document.body.addEventListener("htmx:configRequest", (evento) => {
  const e = /** @type {CustomEvent} */ (evento);
  const token = document.querySelector("meta[name='csrf-token']")?.getAttribute("content");
  if (token) e.detail.headers["X-CSRFToken"] = token;
});

// Formulários: evita duplo envio e mostra "carregando" no botão acionado.
document.addEventListener("submit", (evento) => {
  if (evento.defaultPrevented) return;
  const botao = /** @type {HTMLButtonElement | null} */ (
    /** @type {SubmitEvent} */ (evento).submitter
  );
  if (botao && !botao.hasAttribute("formnovalidate")) {
    window.setTimeout(() => botao.setAttribute("aria-busy", "true"), 0);
  }
});

// Voltar pelo histórico restaura o botão (bfcache).
window.addEventListener("pageshow", () => {
  document.querySelectorAll("[aria-busy='true']").forEach((b) => b.removeAttribute("aria-busy"));
});
