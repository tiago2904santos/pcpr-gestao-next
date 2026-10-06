// @ts-check
/**
 * Janela "anexar via assinada" (componentes/dialogo_assinado.html): um link com
 * `data-anexar-assinado="<url>"` abre a janela única da página com o documento dele.
 * Confere extensão e tamanho antes de enviar (o servidor confere de novo, e também o
 * começo "%PDF-"). Sem JS, o link leva à página de anexar.
 */

const MAXIMO = 15 * 1024 * 1024;

/** @param {number} bytes */
const tamanho = (bytes) => (bytes >= 1024 * 1024
  ? `${(bytes / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
  : `${Math.max(1, Math.round(bytes / 1024))} KB`);

/** Mostra o arquivo escolhido no cartão (ou a área vazia). @param {HTMLElement} janela */
function mostrarArquivo(janela) {
  const campo = /** @type {HTMLInputElement} */ (janela.querySelector("input[type=file]"));
  const arquivo = campo.files && campo.files[0];
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-vazio]")).hidden = Boolean(arquivo);
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-arquivo]")).hidden = !arquivo;
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-area]")).classList.toggle("anexo__area--com-arquivo", Boolean(arquivo));
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-nome]")).textContent = arquivo ? arquivo.name : "";
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-tamanho]")).textContent = arquivo ? tamanho(arquivo.size) : "";
  if (arquivo) {
    /** @type {HTMLElement} */ (janela.querySelector("#dialogo-assinado-erro")).hidden = true;
    campo.removeAttribute("aria-invalid");
  }
}

document.addEventListener("change", (e) => {
  const campo = /** @type {HTMLElement} */ (e.target);
  if (campo.matches("#dialogo-assinado-arquivo")) mostrarArquivo(/** @type {HTMLElement} */ (campo.closest("dialog")));
});

// Soltar o PDF na área: o arquivo vai para o próprio <input type=file> (o envio é o mesmo).
document.addEventListener("dragover", (e) => {
  const area = /** @type {HTMLElement} */ (e.target).closest?.("[data-assinado-area]");
  if (!area) return;
  e.preventDefault();
  area.classList.add("anexo__area--sobre");
});
document.addEventListener("dragleave", (e) => {
  /** @type {HTMLElement} */ (e.target).closest?.("[data-assinado-area]")?.classList.remove("anexo__area--sobre");
});
document.addEventListener("drop", (e) => {
  const area = /** @type {HTMLElement} */ (e.target).closest?.("[data-assinado-area]");
  if (!area) return;
  e.preventDefault();
  area.classList.remove("anexo__area--sobre");
  const campo = /** @type {HTMLInputElement} */ (area.querySelector("input[type=file]"));
  if (e.dataTransfer?.files.length) {
    campo.files = e.dataTransfer.files;
    mostrarArquivo(/** @type {HTMLElement} */ (area.closest("dialog")));
  }
});

/** @param {HTMLElement} janela @param {string} texto */
function mostrarErro(janela, texto) {
  const erro = /** @type {HTMLElement} */ (janela.querySelector("#dialogo-assinado-erro"));
  const campo = /** @type {HTMLInputElement} */ (janela.querySelector("input[type=file]"));
  /** @type {HTMLElement} */ (erro.querySelector("[data-assinado-erro]")).textContent = texto;
  erro.hidden = false;
  campo.setAttribute("aria-invalid", "true");
  campo.focus();
}

document.addEventListener("click", (e) => {
  const botao = /** @type {HTMLElement | null} */ (
    /** @type {HTMLElement} */ (e.target).closest("[data-anexar-assinado]"));
  const janela = /** @type {HTMLDialogElement | null} */ (
    document.getElementById("dialogo-assinado"));
  if (!botao || !janela) return;
  e.preventDefault();
  const form = /** @type {HTMLFormElement} */ (janela.querySelector("form"));
  const campo = /** @type {HTMLInputElement} */ (form.querySelector("input[type=file]"));
  form.action = botao.dataset.anexarAssinado || "";
  form.reset();
  // Para onde voltar: a página de onde se abriu (a lista com o resumo, a folha…).
  const voltar = /** @type {HTMLInputElement | null} */ (form.querySelector("input[name=voltar]"));
  if (voltar && botao.dataset.assinadoVoltar) voltar.value = botao.dataset.assinadoVoltar;
  campo.removeAttribute("aria-invalid");
  /** @type {HTMLElement} */ (janela.querySelector("#dialogo-assinado-erro")).hidden = true;
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-documento]")).textContent =
    botao.dataset.assinadoTitulo || "";
  /** @type {HTMLElement} */ (janela.querySelector("[data-assinado-troca-aviso]")).hidden =
    botao.dataset.assinadoTroca === undefined;
  const menu = /** @type {any} */ (botao.closest("pc-menu"));
  if (menu && typeof menu.fechar === "function") menu.fechar(false);
  mostrarArquivo(janela);
  janela.showModal();
  campo.focus();
});

document.addEventListener("submit", (e) => {
  const form = /** @type {HTMLFormElement} */ (e.target);
  if (!form.matches("[data-assinado-form]")) return;
  const janela = /** @type {HTMLElement} */ (form.closest("dialog"));
  const campo = /** @type {HTMLInputElement} */ (form.querySelector("input[type=file]"));
  const arquivo = campo.files && campo.files[0];
  let erro = "";
  if (!arquivo) erro = "Escolha o PDF assinado.";
  else if (!arquivo.name.toLowerCase().endsWith(".pdf")) erro = "Envie um arquivo PDF.";
  else if (arquivo.size > MAXIMO) erro = "Arquivo maior que 15MB.";
  if (erro) {
    e.preventDefault();
    mostrarErro(janela, erro);
    return;
  }
  const enviar = /** @type {HTMLButtonElement | null} */ (form.querySelector("[type=submit]"));
  if (enviar) {
    enviar.disabled = true;
    enviar.setAttribute("aria-busy", "true");
  }
}, true);

// Gerar o documento abre outra aba; ao voltar, as regiões marcadas se refazem (ex.: a OS
// acabou de ser gerada e já pode receber a via), sem recarregar a página.
document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState !== "visible") return;
  const regioes = Array.from(document.querySelectorAll("[data-atualizar-ao-voltar][id]"));
  if (!regioes.length || document.querySelector("dialog[open]")) return;
  try {
    const resposta = await fetch(window.location.href, { headers: { "X-Requested-With": "fetch" } });
    if (!resposta.ok) return;
    const nova = new DOMParser().parseFromString(await resposta.text(), "text/html");
    for (const regiao of regioes) {
      const substituta = nova.getElementById(regiao.id);
      if (substituta && !regiao.contains(document.activeElement)) regiao.replaceWith(substituta);
    }
  } catch {
    /* sem rede: fica como está */
  }
});

export {};
