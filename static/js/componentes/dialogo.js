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
      d.showModal();
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
