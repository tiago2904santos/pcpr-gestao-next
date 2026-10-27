// @ts-check
/**
 * Diálogos com <dialog> nativo (foco preso, Esc e véu já acessíveis).
 *
 *  - `<button data-abrir-dialogo="id">` abre o <dialog id="id">;
 *  - `<button data-fechar-dialogo>` dentro do diálogo fecha;
 *  - Confirmações do HTMX (`hx-confirm`) usam o diálogo #dialogo-confirmacao
 *    em vez do window.confirm (que não segue o Design System).
 *  - Formulários comuns com `data-confirmar="Mensagem"` também passam pelo diálogo.
 */

/** @param {string} id */
function dialogoPorId(id) {
  return /** @type {HTMLDialogElement | null} */ (document.getElementById(id));
}

/**
 * Fecha com a animação de saída (recolher) e só então chama close().
 * Reentrante: um segundo pedido durante a saída é ignorado.
 * @param {HTMLDialogElement} d @param {string} [valor]
 */
export function fecharDialogo(d, valor) {
  if (!d.open || d.classList.contains("dialogo--saindo")) return;
  d.classList.add("dialogo--saindo");
  let feito = false;
  const fim = () => {
    if (feito) return;
    feito = true;
    d.classList.remove("dialogo--saindo");
    d.close(valor);
  };
  d.addEventListener("animationend", fim, { once: true });
  window.setTimeout(fim, 300); // reduced-motion ou animação indisponível
}

document.addEventListener("click", (e) => {
  const alvo = /** @type {HTMLElement} */ (e.target);
  const abrir = /** @type {HTMLElement | null} */ (alvo.closest("[data-abrir-dialogo]"));
  if (abrir) {
    const d = dialogoPorId(abrir.dataset.abrirDialogo || "");
    if (d) {
      e.preventDefault();
      // A janela secundária usa a própria superfície, sem herdar CSS/foco do resumo.
      if (d.hasAttribute("data-dialogo-secundario") && d.parentElement?.closest("dialog")) {
        const origem = document.createComment("origem do diálogo secundário");
        const retorno = /** @type {HTMLElement | null} */ (document.activeElement);
        d.before(origem);
        document.body.append(d);
        d.addEventListener("close", () => {
          if (origem.isConnected) origem.replaceWith(d);
          else d.remove();
          const foco = retorno?.id ? document.getElementById(retorno.id) : retorno;
          if (foco?.isConnected) foco.focus();
        }, { once: true });
      }
      // Cadastro auxiliar ocupa a mesma etapa visual. O formulário anterior fica no
      // DOM, com seus valores, e volta ao fechar o auxiliar (inclusive por Escape).
      const pai = abrir.closest("dialog[open]");
      if (pai instanceof HTMLDialogElement && pai !== d
          && (d.hasAttribute("data-cadastro-rapido") || d.hasAttribute("data-cadastro-url"))) {
        pai.dataset.cadastroSuspenso = "1";
        pai.close();
        d.addEventListener("close", () => {
          if (!pai.isConnected) return;
          pai.showModal();
          delete pai.dataset.cadastroSuspenso;
          if (abrir.isConnected) abrir.focus({ preventScroll: true });
        }, { once: true });
      }
      d.showModal();
      if (d.dataset.cadastroUrl) {
        import("./cadastro-rapido.js").then((m) => m.carregarFormulario(d, abrir)).catch(() => {
          const aviso = d.querySelector("[data-cadastro-estado]");
          if (aviso) aviso.textContent = "Não foi possível carregar. Feche e abra "
            + "novamente para tentar.";
        });
      }
    }
    return;
  }
  const fechar = alvo.closest("[data-fechar-dialogo]");
  if (fechar) {
    const d = /** @type {HTMLDialogElement | null} */ (fechar.closest("dialog"));
    if (d) fecharDialogo(d);
    return;
  }
  // Botões de <form method="dialog"> (confirmação): saem animados com o mesmo returnValue.
  const botao = /** @type {HTMLButtonElement | null} */ (alvo.closest("form[method=dialog] button"));
  if (botao && !botao.hasAttribute("formmethod")) {
    const d = /** @type {HTMLDialogElement | null} */ (botao.closest("dialog"));
    if (d) {
      e.preventDefault();
      fecharDialogo(d, botao.value);
    }
  }
});

// Janela que o servidor já mandou desenhada e aberta (`data-abrir-ao-carregar`): o resumo
// pedido por outra tela ("?resumo=<pk>") ou a revisão antes de emitir ("?revisar=1").
// Abre na carga, e o endereço perde o parâmetro para recarregar não reabri-la.
const janelaPedida = /** @type {HTMLDialogElement | null} */ (
  document.querySelector("dialog[data-abrir-ao-carregar]")
);
if (janelaPedida) {
  if (janelaPedida.open) janelaPedida.close(); // veio aberta (sem JS ela já serve); vira modal
  janelaPedida.showModal();
  const url = new URL(window.location.href);
  url.searchParams.delete("resumo");
  url.searchParams.delete("revisar");
  window.history.replaceState(null, "", url);
}

// "Pedir motivo" (componentes/dialogo_motivo.html): um botão com data-pedir-motivo abre a
// janela única da página com título, rótulo e ação dele; o texto é obrigatório.
document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (e.target).closest("[data-pedir-motivo]"));
  const janela = dialogoPorId("dialogo-motivo");
  if (!botao || !janela) return;
  e.preventDefault();
  const form = /** @type {HTMLFormElement} */ (janela.querySelector("form"));
  const texto = /** @type {HTMLTextAreaElement} */ (form.querySelector("textarea"));
  const d = botao.dataset;
  form.action = d.pedirMotivo || "";
  texto.name = d.motivoCampo || "motivo";
  texto.value = "";
  /** @type {HTMLElement} */ (janela.querySelector(".dialogo__titulo")).textContent = d.motivoTitulo || "Confirmar";
  /** @type {HTMLElement} */ (janela.querySelector("[data-motivo-rotulo]")).textContent = d.motivoRotulo || "Motivo";
  /** @type {HTMLElement} */ (janela.querySelector("[data-motivo-ajuda]")).textContent = d.motivoAjuda || "Fica registrado no histórico do ofício.";
  const acao = /** @type {HTMLButtonElement} */ (janela.querySelector("[data-motivo-acao]"));
  acao.textContent = d.motivoAcao || "Confirmar";
  const perigo = d.motivoPerigo !== undefined;
  acao.classList.toggle("botao--perigo", perigo);
  acao.classList.toggle("botao--primario", !perigo);
  janela.classList.toggle("dialogo--perigo", perigo);
  /** @type {HTMLElement} */ (janela.querySelector("#dialogo-motivo-erro")).hidden = true;
  const contexto = /** @type {HTMLElement} */ (janela.querySelector("[data-motivo-contexto]"));
  contexto.textContent = d.motivoContexto || "";
  contexto.hidden = !d.motivoContexto;
  texto.removeAttribute("aria-invalid");
  texto.setAttribute("aria-describedby", "dialogo-motivo-ajuda");  // erro escondido não descreve
  // O menu de onde veio não fica aberto por baixo da janela.
  const menu = /** @type {any} */ (botao.closest("pc-menu"));
  if (menu && typeof menu.fechar === "function") menu.fechar(false);
  janela.showModal();
  texto.focus();
});
// "voltar" vivo (F3): a lista muda de endereço sem recarregar (busca ao vivo, HTMX), então
// o endereço gravado na carga da página fica velho. Na hora de enviar, vale o de agora.
document.addEventListener("submit", (e) => {
  const form = /** @type {HTMLFormElement} */ (e.target);
  const voltar = /** @type {HTMLInputElement | null} */ (form.querySelector("input[name=voltar][data-voltar-vivo]"));
  if (voltar) voltar.value = window.location.pathname + window.location.search;
}, true);
document.addEventListener("submit", (e) => {
  const form = /** @type {HTMLFormElement} */ (e.target);
  if (!form.matches("[data-motivo-form]")) return;
  const texto = /** @type {HTMLTextAreaElement} */ (form.querySelector("textarea"));
  if (texto.value.trim()) return;
  e.preventDefault();
  /** @type {HTMLElement} */ (form.querySelector("#dialogo-motivo-erro")).hidden = false;
  texto.setAttribute("aria-invalid", "true");
  texto.setAttribute("aria-describedby", "dialogo-motivo-ajuda dialogo-motivo-erro");
  texto.focus();
}, true);

// Esc: a mesma saída animada (o navegador fecharia na hora).
document.addEventListener("cancel", (e) => {
  const d = /** @type {HTMLDialogElement} */ (e.target);
  if (d instanceof HTMLDialogElement && d.classList.contains("dialogo")) {
    e.preventDefault();
    fecharDialogo(d, "");
  }
}, true);

/**
 * Abre o diálogo de confirmação padrão e resolve com true/false.
 * @param {{titulo?: string, mensagem: string, confirmar?: string, cancelar?: string, perigo?: boolean}} opcoes
 * @returns {Promise<boolean>}
 */
export function confirmar(opcoes) {
  // Uma pergunta por vez: a segunda espera a primeira ser respondida (abrir o mesmo
  // diálogo já aberto dava erro e a pergunta se perdia).
  const vez = filaDeConfirmacoes.then(() => perguntar(opcoes));
  filaDeConfirmacoes = vez.catch(() => false);
  return vez;
}

/** @type {Promise<unknown>} */
let filaDeConfirmacoes = Promise.resolve();

/** @param {{titulo?: string, mensagem: string, confirmar?: string, cancelar?: string, perigo?: boolean}} opcoes
 * @returns {Promise<boolean>} */
function perguntar(opcoes) {
  const d = dialogoPorId("dialogo-confirmacao");
  if (!d) return Promise.resolve(window.confirm(opcoes.mensagem));
  const titulo = /** @type {HTMLElement} */ (d.querySelector("[data-titulo]"));
  const mensagem = /** @type {HTMLElement} */ (d.querySelector("[data-mensagem]"));
  const botao = /** @type {HTMLButtonElement} */ (d.querySelector("[data-confirmar]"));
  titulo.textContent = opcoes.titulo || "Confirmar ação";
  mensagem.textContent = opcoes.mensagem;
  botao.textContent = opcoes.confirmar || "Confirmar";
  const voltar = /** @type {HTMLElement | null} */ (d.querySelector("[data-cancelar]"));
  if (voltar) voltar.textContent = opcoes.cancelar || "Cancelar";
  d.classList.toggle("dialogo--perigo", Boolean(opcoes.perigo));
  botao.classList.toggle("botao--perigo", Boolean(opcoes.perigo));
  botao.classList.toggle("botao--primario", !opcoes.perigo);
  return new Promise((resolver) => {
    d.addEventListener("close", () => resolver(d.returnValue === "confirmar"), { once: true });
    d.returnValue = "";
    d.showModal();
  });
}

document.addEventListener("htmx:confirm", (evento) => {
  const e = /** @type {CustomEvent} */ (evento);
  const pergunta = e.detail.question;
  if (!pergunta) return;
  e.preventDefault();
  const origem = /** @type {HTMLElement} */ (e.detail.elt);
  confirmar({
    titulo: origem.dataset.confirmarTitulo,
    mensagem: pergunta,
    confirmar: origem.dataset.confirmarRotulo,
    perigo: origem.dataset.confirmarPerigo !== undefined,
  }).then((ok) => {
    if (ok) e.detail.issueRequest(true);
  });
});

document.addEventListener("submit", (evento) => {
  const form = /** @type {HTMLFormElement} */ (evento.target);
  const submissor = /** @type {HTMLElement | null} */ (
    /** @type {SubmitEvent} */ (evento).submitter
  );
  const fonte = submissor?.dataset.confirmar ? submissor : form;
  const mensagem = fonte.dataset.confirmar;
  if (!mensagem || form.dataset.confirmado === "1") return;
  evento.preventDefault();
  confirmar({
    titulo: fonte.dataset.confirmarTitulo,
    mensagem,
    confirmar: fonte.dataset.confirmarRotulo,
    perigo: fonte.dataset.confirmarPerigo !== undefined,
  }).then((ok) => {
    if (!ok) return;
    form.dataset.confirmado = "1";
    form.requestSubmit(/** @type {HTMLButtonElement | null} */ (submissor));
    delete form.dataset.confirmado;
  });
});

// Resumo: só consultar geração enquanto a janela está operável. O filtro de hx-trigger
// exigiria eval, desabilitado pela CSP da aplicação; cancelar pelo evento oficial HTMX.
/** @type {WeakMap<XMLHttpRequest, HTMLDialogElement>} */
const pedidosResumo = new WeakMap();
/** @type {WeakMap<HTMLDialogElement, Set<XMLHttpRequest>>} */
const pendentesResumo = new WeakMap();
document.body.addEventListener("htmx:beforeRequest", (evento) => {
  const detalhe = /** @type {CustomEvent} */ (evento).detail;
  const origem = detalhe?.elt;
  if (!(origem instanceof Element) || !origem.matches("[data-resumo-poll]")) return;
  const janela = origem.closest("dialog");
  if (!(janela instanceof HTMLDialogElement)) return;
  if (!janela.open || janela.classList.contains("dialogo--saindo")) {
    evento.preventDefault();
    return;
  }
  const xhr = detalhe.xhr;
  pedidosResumo.set(xhr, janela);
  const pendentes = pendentesResumo.get(janela) || new Set();
  pendentes.add(xhr);
  pendentesResumo.set(janela, pendentes);
});
document.body.addEventListener("htmx:beforeSwap", (evento) => {
  const xhr = /** @type {CustomEvent} */ (evento).detail?.xhr;
  const janela = xhr && pedidosResumo.get(xhr);
  if (janela && (!janela.isConnected || !janela.open
      || janela.classList.contains("dialogo--saindo"))) evento.preventDefault();
});
document.body.addEventListener("htmx:afterRequest", (evento) => {
  const xhr = /** @type {CustomEvent} */ (evento).detail?.xhr;
  const janela = xhr && pedidosResumo.get(xhr);
  if (janela) pendentesResumo.get(janela)?.delete(xhr);
});
document.addEventListener("close", (evento) => {
  const janela = evento.target;
  if (!(janela instanceof HTMLDialogElement)) return;
  pendentesResumo.get(janela)?.forEach((xhr) => xhr.abort());
  pendentesResumo.delete(janela);
}, true);

/** @type {{id: string, menuId: string, janela: HTMLDialogElement} | null} */
let focoRodapeResumo = null;
document.body.addEventListener("htmx:oobBeforeSwap", (evento) => {
  const alvo = /** @type {CustomEvent} */ (evento).detail?.target;
  const foco = document.activeElement;
  if (!(alvo instanceof HTMLElement) || alvo.id !== "resumo-rodape"
      || !(foco instanceof HTMLElement) || !alvo.contains(foco)) return;
  const janela = alvo.closest("dialog");
  if (janela instanceof HTMLDialogElement) {
    const gatilho = foco.closest("pc-menu")?.querySelector("[data-menu-botao]");
    focoRodapeResumo = { id: foco.id, janela,
      menuId: gatilho instanceof HTMLElement ? gatilho.id : "" };
  }
});
document.body.addEventListener("htmx:oobAfterSwap", (evento) => {
  if (/** @type {CustomEvent} */ (evento).detail?.target?.id !== "resumo-rodape") return;
  const antes = focoRodapeResumo;
  focoRodapeResumo = null;
  if (!antes?.janela.open || antes.janela.classList.contains("dialogo--saindo")) return;
  if (document.activeElement !== document.body && document.activeElement?.isConnected) return;
  const rodape = document.getElementById("resumo-rodape");
  const novo = antes.id && document.getElementById(antes.id);
  if (novo instanceof HTMLElement && rodape?.contains(novo)
      && !novo.closest("[hidden]") && novo.getClientRects().length
      && getComputedStyle(novo).visibility !== "hidden") novo.focus({ preventScroll: true });
  else {
    // O menu recém-renderizado pode estar fechado: um item oculto não recebe foco.
    const gatilho = antes.menuId && document.getElementById(antes.menuId);
    if (gatilho instanceof HTMLElement && rodape?.contains(gatilho)) {
      gatilho.focus({ preventScroll: true });
    } else rodape?.focus({ preventScroll: true });
  }
});
