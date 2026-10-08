// @ts-check
/**
 * Cadastro rápido: o "+" ao lado de uma escolha abre um diálogo por cima do que está
 * aberto, grava o registro e o devolve já escolhido — sem recarregar a página, que levaria
 * junto o que a pessoa tinha digitado.
 *
 * Marcação: `<dialog data-cadastro-rapido>` com um <form> que posta no mesmo endpoint da
 * tela de cadastro. A view responde JSON ({id, nome, meta?}) quando o pedido diz
 * `Accept: application/json` — é o que este arquivo manda.
 *
 * O que fazer com o registro criado, por atributo do <dialog>:
 *  - `data-destino="<id do select>"` → entra como opção e fica escolhido (viatura, cargo…);
 *    com `data-valor="nome"`, o valor da opção é o nome, não o id (o horário do plano);
 *    com `data-sem-escolher`, só entra na lista (o conjunto de atividades: escolher já o
 *    aplicaria); `ids` da resposta vira `data-ids` da opção;
 *  - `data-envio-url="<url>"` + `data-alvo="<seletor>"` → manda o id por HTMX e troca o
 *    pedaço devolvido (a equipe do ofício: o servidor novo já entra na equipe);
 *  - `data-multiescolha="<seletor>"` → entra como cartão num <pc-multiescolha> (a equipe
 *    do termo, que vai junto com o formulário).
 *
 * Antes de tudo vale o campo de onde o "+" foi apertado: o <pc-multiescolha> ou o <select>
 * ao lado dele. Assim uma tela com várias equipes (o lote) põe o criado na certa.
 */

import { fecharDialogo } from "./dialogo.js";

/** O "+" que abriu cada diálogo (o campo ao lado dele é quem recebe o criado). */
const origens = new WeakMap();
/** @type {Map<string, Promise<void>>} */
const carregamentos = new Map();

/** @param {HTMLDialogElement} janela @param {HTMLElement} origem */
export async function carregarFormulario(janela, origem) {
  origens.set(janela, origem);
  const url = janela.dataset.cadastroUrl;
  if (!url) return;
  try {
    let carregamento = carregamentos.get(url);
    if (!carregamento) {
      carregamento = (async () => {
        const resposta = await fetch(url, { credentials: "same-origin",
          headers: { "X-Requested-With": "fetch" } });
        if (!resposta.ok || resposta.redirected) throw new Error("Formulário indisponível");
        const recebido = new DOMParser().parseFromString(await resposta.text(), "text/html");
        const destinos = /** @type {HTMLDialogElement[]} */ (Array.from(
          document.querySelectorAll("dialog[data-cadastro-url]"))).filter(
          (d) => d.dataset.cadastroUrl === url);
        // Validar o pacote inteiro antes de trocar qualquer diálogo.
        const pares = destinos.map((d) => [d, recebido.getElementById(d.id)]);
        if (pares.some(([, fonte]) => !fonte?.matches("dialog[data-cadastro-rapido]")
            || !fonte.querySelector("form"))) throw new Error("Formulário incompleto");
        const focada = destinos.find((d) => d.contains(document.activeElement));
        for (const [destino, fonte] of pares) {
          if (!(destino instanceof HTMLDialogElement) || !fonte) continue;
          destino.innerHTML = fonte.innerHTML;
          for (const atributo of fonte.attributes) {
            if (atributo.name !== "open") destino.setAttribute(atributo.name, atributo.value);
          }
          destino.removeAttribute("data-cadastro-url");
          ligar(destino);
          /** @type {any} */ (window).htmx?.process(destino);
        }
        document.dispatchEvent(new CustomEvent("pcpr:pagina-refeita"));
        document.dispatchEvent(new CustomEvent("pcpr:controladores-repostos"));
        const primeiro = focada?.querySelector("input:not([type='hidden'])");
        if (focada?.open && primeiro instanceof HTMLElement) primeiro.focus();
      })();
      carregamentos.set(url, carregamento);
    }
    await carregamento;
  } catch {
    carregamentos.delete(url);
    const aviso = janela.querySelector("[data-cadastro-estado]");
    if (aviso) aviso.textContent = "Não foi possível carregar o formulário. Feche e abra "
      + "novamente para tentar. Se a sessão expirou, entre de novo.";
  }
}
document.addEventListener("click", (evento) => {
  const botao = /** @type {HTMLElement} */ (evento.target).closest?.("[data-abrir-dialogo]");
  const janela = botao && document.getElementById(/** @type {HTMLElement} */ (botao).dataset.abrirDialogo || "");
  if (janela?.matches("dialog[data-cadastro-rapido]")) origens.set(janela, botao);
}, true);

/** @param {string} mensagem @param {string} [nivel] */
function avisar(mensagem, nivel = "sucesso") {
  document.body.dispatchEvent(new CustomEvent("toast", { detail: { mensagem, nivel } }));
}

/** @param {HTMLFormElement} form @param {string} mensagem */
function mostrarErro(form, mensagem) {
  let erro = /** @type {HTMLElement | null} */ (form.querySelector("[data-erro]"));
  if (!erro) {
    // Os diálogos vindos das telas de cadastro não trazem lugar para o erro: cria um.
    erro = document.createElement("p");
    erro.className = "campo__erro";
    erro.setAttribute("data-erro", "");
    form.querySelector(".dialogo__corpo")?.prepend(erro);
  }
  erro.textContent = mensagem;
  erro.hidden = !mensagem;
  if (mensagem) erro.scrollIntoView({ block: "nearest" });
}

/** @param {HTMLDialogElement} janela */
function ligar(janela) {
  if (janela.dataset.pronto) return;
  const form = /** @type {HTMLFormElement | null} */ (janela.querySelector("form"));
  if (!form) return;
  janela.dataset.pronto = "1";

  // Fechar devolve o formulário em branco: a próxima vez começa limpa.
  janela.addEventListener("close", () => { form.reset(); mostrarErro(form, ""); });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const enviar = /** @type {HTMLButtonElement | null} */ (
      form.querySelector("button[type='submit'].botao--primario"));
    if (enviar) enviar.disabled = true;
    const resposta = await fetch(form.action, {
      method: "POST", body: new FormData(form), credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "fetch" },
    }).catch(() => null);
    if (enviar) enviar.disabled = false;
    const corpo = resposta ? await resposta.json().catch(() => ({})) : {};
    if (!resposta || !resposta.ok) {
      mostrarErro(form, corpo.erro || "Não foi possível cadastrar agora. Tente de novo.");
      return;
    }
    aplicar(janela, corpo);
    fecharDialogo(janela);
    avisar(`“${corpo.nome}” cadastrado.`);
  });
}

/** @param {HTMLDialogElement} janela @param {{id: number, nome: string, meta?: string, ids?: string}} novo */
function aplicar(janela, novo) {
  const origem = /** @type {HTMLElement | undefined} */ (origens.get(janela));
  const multiOrigem = /** @type {any} */ (origem?.closest("pc-multiescolha"));
  if (multiOrigem?.adicionar) {
    multiOrigem.adicionar({ id: String(novo.id), titulo: novo.nome, meta: novo.meta });
    return;
  }
  const destino = /** @type {HTMLSelectElement | null} */ (
    origem?.closest(".campo__com-acao")?.querySelector("select")
    || document.getElementById(janela.dataset.destino || ""));
  if (destino) {
    const valor = janela.dataset.valor === "nome" ? novo.nome : String(novo.id);
    const escolher = !janela.hasAttribute("data-sem-escolher");
    const opcao = new Option(novo.nome, valor, escolher, escolher);
    if (novo.ids) opcao.dataset.ids = novo.ids;
    destino.add(opcao);
    // O <pc-select>/<pc-combobox> que embrulha a escolha acompanha pelo "change".
    if (escolher) destino.dispatchEvent(new Event("change", { bubbles: true }));
  }
  // Seletor múltiplo (a equipe do termo): o criado entra como mais um cartão.
  const multi = /** @type {any} */ (janela.dataset.multiescolha
    ? document.querySelector(janela.dataset.multiescolha) : null);
  if (multi?.adicionar) multi.adicionar({ id: String(novo.id), titulo: novo.nome, meta: novo.meta });
  const url = janela.dataset.envioUrl;
  const htmx = /** @type {any} */ (window).htmx;
  if (url && htmx) {
    htmx.ajax("POST", url, {
      target: janela.dataset.alvo || undefined,
      swap: janela.dataset.troca || "outerHTML",
      values: { id: novo.id },
    });
  }
}

document.querySelectorAll("dialog[data-cadastro-rapido]").forEach(
  (d) => ligar(/** @type {HTMLDialogElement} */ (d)));
