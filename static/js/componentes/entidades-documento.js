// @ts-check
/**
 * O que vem do cadastro, dentro do documento (servidor, motorista, transporte — marcados com
 * `data-entidade` no modelo), abre a peça do formulário que o altera:
 *
 *  - um clique no documento (editor-documento.js avisa com `pc-editor:entidade`) abre um
 *    menu pequeno junto do trecho: "Alterar a equipe", "Editar cadastro de Fulano"…;
 *  - "Alterar …" abre uma janela com o PRÓPRIO bloco da folha (Equipe ou Transporte): o
 *    bloco é levado para a janela e devolvido ao lugar quando ela fecha — o mesmo
 *    componente, com as mesmas regras e gravações, nada copiado;
 *  - "Editar cadastro" abre a janela de cadastro (a de Cadastros) já preenchida com o
 *    registro; gravar atualiza a equipe ou o transporte da folha.
 * Ao fechar, se algo mudou, o documento é refeito com os dados novos (o "Atualizar").
 */
import { fecharDialogo } from "./dialogo.js";
import { icone } from "./menu.js";

/** @typedef {{tipo: string, id: string, nome: string, caixa: {left: number, top: number, bottom: number, width: number}, editor: HTMLElement}} Entidade */

/**
 * As partes da folha que abrem na janela: onde estão e o título.
 * @type {Record<string, {achar: () => HTMLElement | null, titulo: string, nota: string, icone: string, tamanho?: string}>}
 */
const BLOCOS = {
  equipe: {
    achar: () => document.getElementById("equipe"), titulo: "Equipe", icone: "users",
    nota: "Quem viaja e quem dirige. A equipe é salva na hora.",
  },
  transporte: {
    achar: () => document.getElementById("transporte"), titulo: "Transporte", icone: "car",
    nota: "Meio de transporte, viatura e porte de arma.",
  },
  identificacao: {
    achar: () => /** @type {HTMLElement | null} */ (document.querySelector("#dados [name='marcador']")?.closest(".campos") ?? null),
    titulo: "Identificação", icone: "file-pen-line", tamanho: "medio",
    nota: "Número, data, protocolo, tipo de documento e custeio.",
  },
  roteiro: {
    achar: () => document.querySelector("#roteiro > .secao__conteudo"), titulo: "Roteiro e diárias",
    icone: "route", tamanho: "amplo", nota: "Sede, destinos, trechos e horários. As diárias acompanham.",
  },
};

/** @type {HTMLElement | null} */
let menu = null;

/** O documento (iframe) onde o menu foi aberto: digitar ou clicar nele fecha o menu. */
/** @type {Document | null} */
let docDoMenu = null;

function fecharMenu() {
  menu?.remove();
  menu = null;
  document.removeEventListener("pointerdown", foraDoMenu, true);
  docDoMenu?.removeEventListener("keydown", fecharMenu, true);
  docDoMenu?.removeEventListener("pointerdown", fecharMenu, true);
  docDoMenu = null;
  window.removeEventListener("scroll", fecharMenu, true);
}

/** @param {Event} e */
function foraDoMenu(e) {
  if (menu && !menu.contains(/** @type {Node} */ (e.target))) fecharMenu();
}

/** @param {string} texto */
const escapar = (texto) => texto.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] || c);

/** As ações de cada trecho; só entram as que a página tem como cumprir. @param {Entidade} e */
function acoesDe(e) {
  /** @type {{rotulo: string, icone: string, fazer: () => void}[]} */
  const acoes = [];
  const temEquipe = Boolean(BLOCOS.equipe.achar());
  const temTransporte = Boolean(BLOCOS.transporte.achar());
  if ((e.tipo === "servidor" || e.tipo === "motorista") && temEquipe) {
    acoes.push({ rotulo: e.tipo === "motorista" ? "Trocar quem dirige" : "Alterar a equipe", icone: "users", fazer: () => abrirBloco("equipe", e.editor) });
  }
  if (e.tipo === "servidor" && e.id) {
    acoes.push({ rotulo: `Editar cadastro de ${e.nome.split(" ")[0]}`, icone: "pencil", fazer: () => editarCadastro("servidor", e.id, e.editor) });
  }
  if ((e.tipo === "transporte" || e.tipo === "motorista") && temTransporte) {
    acoes.push({ rotulo: "Alterar o transporte", icone: "car", fazer: () => abrirBloco("transporte", e.editor) });
  }
  if (e.tipo === "transporte" && e.id) {
    acoes.push({ rotulo: "Editar cadastro da viatura", icone: "pencil", fazer: () => editarCadastro("viatura", e.id, e.editor) });
  }
  if (e.tipo === "identificacao" && BLOCOS.identificacao.achar()) {
    acoes.push({ rotulo: "Alterar a identificação e o custeio", icone: "file-pen-line", fazer: () => abrirBloco("identificacao", e.editor) });
  }
  if (e.tipo === "roteiro" && BLOCOS.roteiro.achar()) {
    acoes.push({ rotulo: "Alterar destinos, trechos e horários", icone: "route", fazer: () => abrirBloco("roteiro", e.editor) });
  }
  if (e.tipo === "configuracao" && e.editor.dataset.configuracao) {
    acoes.push({ rotulo: "Editar na configuração da unidade", icone: "settings", fazer: () => abrirConfiguracao(e.editor) });
  }
  return acoes;
}

/**
 * Assinatura, destinatário, cabeçalho e rodapé vêm da configuração da unidade (vale para
 * todos os documentos): ela abre em outra aba e, ao voltar para cá, o documento é refeito.
 * @param {HTMLElement} editor
 */
function abrirConfiguracao(editor) {
  const url = editor.dataset.configuracao;
  if (!url) return;
  window.open(url, "_blank", "noopener");
  const aoVoltar = () => {
    if (document.visibilityState !== "visible") return;
    document.removeEventListener("visibilitychange", aoVoltar);
    refazer(editor);
  };
  document.addEventListener("visibilitychange", aoVoltar);
}

/** @param {Entidade} e */
function abrirMenu(e) {
  fecharMenu();
  const acoes = acoesDe(e);
  if (!acoes.length) return;
  menu = document.createElement("div");
  menu.className = "menu__painel entidade-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", e.nome || "Dado do cadastro");
  menu.innerHTML = `<p class="entidade-menu__titulo">${escapar(e.nome || "")}</p>`;
  acoes.forEach((a, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "menu__item";
    b.setAttribute("role", "menuitem");
    b.innerHTML = `${icone(a.icone).outerHTML}<span>${escapar(a.rotulo)}</span>`;
    b.addEventListener("click", () => { fecharMenu(); a.fazer(); });
    b.addEventListener("keydown", (ev) => {
      const itens = /** @type {HTMLElement[]} */ (Array.from(menu?.querySelectorAll(".menu__item") || []));
      if (ev.key === "ArrowDown") { ev.preventDefault(); itens[(i + 1) % itens.length]?.focus(); }
      if (ev.key === "ArrowUp") { ev.preventDefault(); itens[(i - 1 + itens.length) % itens.length]?.focus(); }
      if (ev.key === "Escape") { ev.preventDefault(); fecharMenu(); }
    });
    menu?.append(b);
  });
  document.body.append(menu);
  // Junto do trecho, por baixo; sem espaço, por cima. Nunca sai da janela.
  const largura = menu.offsetWidth;
  const altura = menu.offsetHeight;
  const esquerda = Math.max(8, Math.min(e.caixa.left, window.innerWidth - largura - 8));
  const embaixo = e.caixa.bottom + 6 + altura < window.innerHeight;
  menu.style.left = `${esquerda}px`;
  menu.style.top = `${embaixo ? e.caixa.bottom + 6 : Math.max(8, e.caixa.top - altura - 6)}px`;
  // Só um atalho: o cursor continua no texto (escrever à vontade é sempre possível) e o
  // menu some assim que se digita ou se clica de novo no documento.
  docDoMenu = /** @type {HTMLIFrameElement | null} */ (e.editor.querySelector("iframe[data-quadro='texto']"))?.contentDocument || null;
  docDoMenu?.addEventListener("keydown", fecharMenu, true);
  docDoMenu?.addEventListener("pointerdown", fecharMenu, true);
  document.addEventListener("pointerdown", foraDoMenu, true);
  window.addEventListener("scroll", fecharMenu, true);
}

/** Refaz o documento do editor com os dados de agora (o botão "Atualizar" da barra). @param {HTMLElement} editor */
function refazer(editor) {
  /** @type {HTMLButtonElement | null} */ (editor.querySelector("[data-acao='atualizar']"))?.click();
}

/** A janela que recebe um bloco da folha. */
function janelaDoBloco() {
  let d = /** @type {HTMLDialogElement | null} */ (document.getElementById("dialogo-bloco-folha"));
  if (d) return d;
  d = document.createElement("dialog");
  d.id = "dialogo-bloco-folha";
  d.className = "dialogo dialogo--largo dialogo--bloco-folha";
  d.setAttribute("aria-labelledby", "dialogo-bloco-folha-titulo");
  d.setAttribute("aria-describedby", "dialogo-bloco-folha-nota");
  d.innerHTML = `
    <div class="dialogo__cabecalho">
      <div class="dialogo__icone" data-icone></div>
      <div class="dialogo__cabecalho-texto"><h2 class="dialogo__titulo" id="dialogo-bloco-folha-titulo"></h2>
        <p class="texto-secundario texto-sm" id="dialogo-bloco-folha-nota" data-nota></p></div>
      <button type="button" class="botao botao--icone dialogo__fechar" data-fechar-dialogo aria-label="Fechar">${icone("x").outerHTML}</button>
    </div>
    <div class="dialogo__corpo documento documento--preparacao" data-corpo></div>
    <div class="dialogo__rodape">
      <p class="dialogo-bloco__salvo">${icone("check-circle-2", "icone icone--sm").outerHTML}Salvo automaticamente · o documento é refeito ao concluir</p>
      <button type="button" class="botao botao--primario" data-fechar-dialogo>${icone("check").outerHTML}Concluir</button>
    </div>`;
  document.body.append(d);
  return d;
}

/**
 * Leva a parte da folha (Equipe, Transporte, Identificação, Roteiro) para a janela e a
 * devolve ao fechar.
 * @param {string} nome @param {HTMLElement} editor
 */
function abrirBloco(nome, editor) {
  const alvo = BLOCOS[nome];
  const bloco = alvo?.achar();
  if (!alvo || !bloco) return;
  const id = bloco.id;
  const d = janelaDoBloco();
  d.classList.toggle("dialogo--bloco-amplo", alvo.tamanho === "amplo");
  d.classList.toggle("dialogo--bloco-medio", alvo.tamanho === "medio");
  d.dataset.bloco = nome;
  const corpo = /** @type {HTMLElement} */ (d.querySelector("[data-corpo]"));
  /** @type {HTMLElement} */ (d.querySelector(".dialogo__titulo")).textContent = alvo.titulo;
  /** @type {HTMLElement} */ (d.querySelector("[data-nota]")).textContent = alvo.nota;
  /** @type {HTMLElement} */ (d.querySelector("[data-icone]")).replaceChildren(icone(alvo.icone));
  const lugar = document.createComment(`lugar de ${nome}`);
  bloco.before(lugar);
  corpo.append(bloco);
  let mudou = false;
  const marcar = () => { mudou = true; };
  const eventos = ["change", "input", "htmx:afterSwap", "pc-equipe-alterada"];
  eventos.forEach((ev) => d.addEventListener(ev, marcar));
  d.addEventListener("close", () => {
    eventos.forEach((ev) => d.removeEventListener(ev, marcar));
    // O HTMX pode ter trocado o bloco enquanto estava aqui: devolve o que estiver agora.
    const atual = (id && document.getElementById(id)) || (bloco.isConnected ? bloco : null);
    if (atual) lugar.replaceWith(atual); else lugar.remove();
    if (mudou) refazer(editor);
  }, { once: true });
  d.showModal();
}

/** Recarrega um bloco da folha a partir da página no servidor (o cadastro mudou). @param {string} id */
async function recarregarBloco(id) {
  const atual = document.getElementById(id);
  if (!atual) return;
  const r = await fetch(window.location.pathname, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } }).catch(() => null);
  if (!r || !r.ok) return;
  const novo = new DOMParser().parseFromString(await r.text(), "text/html").getElementById(id);
  if (!novo) return;
  const importado = /** @type {HTMLElement} */ (document.importNode(novo, true));
  atual.replaceWith(importado);
  /** @type {any} */ (window).htmx?.process(importado);
}

/**
 * Abre a janela de cadastro (servidor ou viatura) preenchida com o registro. O formulário
 * de "novo" sai da janela enquanto ela edita e volta quando ela fecha.
 * @param {"servidor" | "viatura"} tipo @param {string} id @param {HTMLElement} editor
 */
async function editarCadastro(tipo, id, editor) {
  const janela = /** @type {HTMLDialogElement | null} */ (document.getElementById(`dialogo-${tipo}`));
  const modelo = tipo === "servidor" ? editor.dataset.editarServidor : editor.dataset.editarViatura;
  if (!janela || !modelo) return;
  const url = modelo.replace("/0/", `/${encodeURIComponent(id)}/`);
  const r = await fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } }).catch(() => null);
  if (!r || !r.ok || r.redirected) return;
  const html = new DOMParser().parseFromString(await r.text(), "text/html");
  const recebido = html.querySelector("dialog form");
  if (!recebido) return;
  const form = /** @type {HTMLFormElement} */ (document.importNode(recebido, true));
  // O que a janela tinha (o formulário de "novo", ou ainda só o aviso de carregar) sai inteiro
  // e volta ao fechar — com os ouvintes que já tinha.
  const guardado = document.createDocumentFragment();
  while (janela.firstChild) guardado.append(janela.firstChild);
  janela.append(form);
  /** @type {any} */ (window).htmx?.process(form);
  document.dispatchEvent(new CustomEvent("pcpr:controladores-repostos"));
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const enviar = /** @type {HTMLButtonElement | null} */ (form.querySelector("button[type='submit'].botao--primario"));
    if (enviar) enviar.disabled = true;
    const resposta = await fetch(form.action, {
      method: "POST", body: new FormData(form), credentials: "same-origin",
      headers: { Accept: "application/json", "X-Requested-With": "fetch" },
    }).catch(() => null);
    if (enviar) enviar.disabled = false;
    const corpo = resposta ? await resposta.json().catch(() => ({})) : {};
    if (!resposta || !resposta.ok) {
      let erro = /** @type {HTMLElement | null} */ (form.querySelector("[data-erro-edicao]"));
      if (!erro) {
        erro = document.createElement("p");
        erro.className = "campo__erro";
        erro.setAttribute("data-erro-edicao", "");
        form.querySelector(".dialogo__corpo")?.prepend(erro);
      }
      erro.textContent = corpo.erro || "Não foi possível salvar agora. Tente de novo.";
      return;
    }
    fecharDialogo(janela);
    await recarregarBloco(tipo === "servidor" ? "equipe" : "transporte");
    refazer(editor);
  });
  janela.addEventListener("close", () => { form.remove(); janela.append(guardado); }, { once: true });
  janela.showModal();
}

document.addEventListener("pc-editor:entidade", (ev) => {
  const d = /** @type {CustomEvent} */ (ev).detail;
  if (d) abrirMenu({ ...d, editor: /** @type {HTMLElement} */ (ev.target) });
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && menu) fecharMenu(); });

export {};
