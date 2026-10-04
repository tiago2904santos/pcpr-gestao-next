// @ts-check
/**
 * Janela "Baixar documentos" (componentes/dialogo_baixar.html). Um botão com
 * `data-baixar-documentos="<url>"` abre; a lista vem do servidor (GET na url, JSON) e todos
 * começam marcados. O envio é por fetch: o arquivo baixa sozinho; se o servidor responder
 * com redirecionamento (uma mensagem de erro), a página vai até lá. Sem JS: sem janela.
 */
import { fecharDialogo } from "./dialogo.js";

const CHAVE = "baixar-documentos:escolhas";

/** @typedef {{valor: string, nome: string, detalhe: string, estado: string, assinado: boolean}} Item */

/** @param {HTMLElement} raiz @param {string} seletor */
const um = (raiz, seletor) => /** @type {HTMLElement} */ (raiz.querySelector(seletor));

function lembradas() {
  try {
    return JSON.parse(window.localStorage.getItem(CHAVE) || "{}");
  } catch {
    return {};
  }
}

/** @param {HTMLFormElement} form */
function lembrar(form) {
  const dados = new FormData(form);
  try {
    window.localStorage.setItem(CHAVE, JSON.stringify({
      formato: dados.get("formato"), versao: dados.get("versao"), saida: dados.get("saida"),
    }));
  } catch {
    /* navegação privada: sem memória */
  }
}

/** @param {HTMLFormElement} form */
function atualizar(form) {
  const marcados = /** @type {HTMLInputElement[]} */ (
    Array.from(form.querySelectorAll("input[name=itens]:checked")));
  const todos = form.querySelectorAll("input[name=itens]");
  const pdf = /** @type {HTMLInputElement} */ (form.querySelector("#baixar-pdf")).checked;
  um(form, "[data-baixar-versao]").hidden = !(pdf && marcados.some((m) => m.dataset.assinado === "1"));
  const unico = /** @type {HTMLInputElement} */ (form.querySelector("#baixar-unico"));
  unico.disabled = !pdf || marcados.length < 2;
  if (unico.disabled && unico.checked) {
    /** @type {HTMLInputElement} */ (form.querySelector("#baixar-separados")).checked = true;
  }
  /** @type {HTMLButtonElement} */ (um(form, "[data-baixar-enviar]")).disabled = !marcados.length;
  um(form, "[data-baixar-todos]").textContent =
    marcados.length === todos.length ? "Desmarcar todos" : "Marcar todos";
}

/** @param {HTMLElement} caixa @param {Item[]} itens */
function desenhar(caixa, itens) {
  caixa.replaceChildren(...itens.map((item, i) => {
    const rotulo = document.createElement("label");
    rotulo.className = "caixas__item escolha";
    rotulo.htmlFor = `baixar-item-${i}`;
    const entrada = document.createElement("input");
    Object.assign(entrada, { type: "checkbox", name: "itens", value: item.valor, checked: true,
      id: `baixar-item-${i}` });
    entrada.dataset.assinado = item.assinado ? "1" : "0";
    const texto = document.createElement("span");
    const nome = document.createElement("strong");
    nome.textContent = item.nome;
    const detalhe = document.createElement("span");
    detalhe.className = "escolha__descricao";
    detalhe.textContent = [item.detalhe, item.estado].filter(Boolean).join(" · ");
    texto.append(nome, detalhe);
    rotulo.append(entrada, texto);
    return rotulo;
  }));
}

/** @param {Response} resposta */
function nomeDoArquivo(resposta) {
  const disposicao = resposta.headers.get("Content-Disposition") || "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposicao);
  if (utf8) return decodeURIComponent(utf8[1]);
  const simples = /filename="?([^";]+)"?/i.exec(disposicao);
  return simples ? simples[1] : "documentos";
}

document.addEventListener("click", async (e) => {
  const alvo = /** @type {HTMLElement} */ (e.target);
  const botao = /** @type {HTMLElement | null} */ (alvo.closest("[data-baixar-documentos]"));
  const janela = /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-baixar"));
  if (!janela) return;
  const form = /** @type {HTMLFormElement} */ (janela.querySelector("form"));
  if (alvo.closest("[data-baixar-todos]")) {
    const caixas = /** @type {HTMLInputElement[]} */ (Array.from(form.querySelectorAll("input[name=itens]")));
    const marcar = caixas.some((c) => !c.checked);
    caixas.forEach((c) => { c.checked = marcar; });
    atualizar(form);
    return;
  }
  if (!botao) return;
  e.preventDefault();
  const url = botao.dataset.baixarDocumentos || "";
  form.reset();
  form.action = url;
  const voltar = /** @type {HTMLInputElement} */ (form.querySelector("input[name=voltar]"));
  voltar.value = window.location.pathname + window.location.search;
  const escolhas = lembradas();
  for (const nome of ["formato", "versao", "saida"]) {
    const opcao = /** @type {HTMLInputElement | null} */ (
      form.querySelector(`input[name=${nome}][value="${escolhas[nome]}"]`));
    if (opcao) opcao.checked = true;
  }
  um(form, "[data-baixar-subtitulo]").textContent = botao.dataset.baixarTitulo || "";
  um(form, "[data-baixar-erro]").hidden = true;
  um(form, "[data-baixar-gerando]").hidden = true;
  const caixa = um(form, "[data-baixar-itens]");
  caixa.replaceChildren();
  const carregando = um(form, "[data-baixar-carregando]");
  carregando.hidden = false;
  const menu = /** @type {any} */ (botao.closest("pc-menu"));
  if (menu && typeof menu.fechar === "function") menu.fechar(false);
  janela.showModal();
  // Enquanto a lista não chega, só o "Baixar" fica parado: recalcular as regras agora
  // (sem itens) desfaria a escolha lembrada de "um PDF só".
  /** @type {HTMLButtonElement} */ (um(form, "[data-baixar-enviar]")).disabled = true;
  try {
    const resposta = await fetch(url, { headers: { Accept: "application/json" } });
    if (resposta.redirected) { window.location.href = resposta.url; return; }
    if (!resposta.ok) throw new Error(String(resposta.status));
    desenhar(caixa, (await resposta.json()).itens);
  } catch {
    const erro = um(form, "[data-baixar-erro]");
    erro.textContent = "Não foi possível carregar os documentos. Tente de novo.";
    erro.hidden = false;
  } finally {
    carregando.hidden = true;
    atualizar(form);
  }
  /** @type {HTMLElement | null} */ (caixa.querySelector("input"))?.focus();
});

document.addEventListener("change", (e) => {
  const form = /** @type {HTMLElement} */ (e.target).closest("form[data-baixar-form]");
  if (form) atualizar(/** @type {HTMLFormElement} */ (form));
});

document.addEventListener("submit", async (e) => {
  const form = /** @type {HTMLFormElement} */ (e.target);
  if (!form.matches("[data-baixar-form]")) return;
  e.preventDefault();
  const janela = /** @type {HTMLDialogElement} */ (form.closest("dialog"));
  const enviar = /** @type {HTMLButtonElement} */ (um(form, "[data-baixar-enviar]"));
  const erro = um(form, "[data-baixar-erro]");
  lembrar(form);
  enviar.disabled = true;
  enviar.setAttribute("aria-busy", "true");
  um(form, "[data-baixar-gerando]").hidden = false;
  erro.hidden = true;
  try {
    const resposta = await fetch(form.action, {
      method: "POST", body: new FormData(form), headers: { "X-Requested-With": "fetch" },
    });
    const disposicao = resposta.headers.get("Content-Disposition") || "";
    if (resposta.ok && /attachment|inline/i.test(disposicao)) {
      const url = URL.createObjectURL(await resposta.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = nomeDoArquivo(resposta);
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
      fecharDialogo(janela);
    } else if (resposta.redirected || resposta.ok) {
      window.location.href = resposta.url;  // mensagem do servidor (ex.: nada marcado)
    } else {
      erro.textContent = resposta.status === 403
        ? "Você não tem permissão para baixar estes documentos."
        : "Não foi possível gerar os documentos. Tente de novo.";
      erro.hidden = false;
    }
  } catch {
    erro.textContent = "Não foi possível gerar os documentos. Tente de novo.";
    erro.hidden = false;
  } finally {
    enviar.disabled = false;
    enviar.removeAttribute("aria-busy");
    um(form, "[data-baixar-gerando]").hidden = true;
  }
});
