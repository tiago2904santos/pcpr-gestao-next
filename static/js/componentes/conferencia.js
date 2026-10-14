// @ts-check
export {};
/**
 * Conferência do cadastro (componentes/prontidao_documental.html): cada pendência leva até o
 * que falta. Em vez do salto seco da âncora, a folha desliza até a seção e acende, por alguns
 * segundos, os campos vazios a que a pendência se refere (pelo rótulo; sem par, os exigidos
 * para emitir e os obrigatórios), e o primeiro já recebe o cursor. Sem campo vazio identificável (ex.: falta
 * equipe), a seção inteira é que acende. Com movimento reduzido, vai direto, sem deslizar.
 */

const DURACAO = 4000;
const calmo = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** O campo está vazio? Olha todos os controles dele, inclusive o valor oculto das listas. @param {Element} campo */
function vazio(campo) {
  const controles = Array.from(campo.querySelectorAll("input:not([type='checkbox']):not([type='radio']), select, textarea"));
  return controles.length > 0 && controles.every((c) => !(/** @type {HTMLInputElement} */ (c).value || "").trim());
}

/** Texto sem acento e em minúsculas, para comparar a pendência com os rótulos. @param {string} t */
const normal = (t) => t.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
const VAZIAS = new Set(["informe", "falta", "faltam", "para", "preencha", "escolha", "selecione", "ainda", "cidade"]);

/** Campos visíveis e vazios da seção. @param {Element} secao */
function vaziosDa(secao) {
  return Array.from(secao.querySelectorAll(".campo"))
    .filter((campo) => campo.querySelector(":scope > .campo__rotulo"))
    .filter((campo) => !campo.closest("[hidden]") && /** @type {HTMLElement} */ (campo).offsetParent !== null)
    .filter(vazio);
}

/**
 * O que falta na seção: primeiro, os campos vazios cujo rótulo aparece na própria pendência
 * ("Informe o efetivo (cargo e quantidade)" → Cargo, Quantidade); sem par, os vazios marcados
 * "(para emitir)" ou obrigatórios — nunca os "(opcional)".
 * @param {Element} secao @param {string} mensagem
 */
function faltando(secao, mensagem) {
  const campos = vaziosDa(secao);
  const palavras = (normal(mensagem).match(/[a-z]{4,}/g) || []).filter((p) => !VAZIAS.has(p));
  const rotulo = (/** @type {Element} */ campo) => normal(campo.querySelector(":scope > .campo__rotulo")?.textContent || "");
  const pelaMensagem = campos.filter((campo) => {
    const r = rotulo(campo);
    return palavras.some((p) => r.includes(p.slice(0, Math.max(4, p.length - 1))));
  });
  if (pelaMensagem.length) return pelaMensagem;
  return campos.filter((campo) => {
    const marca = campo.querySelector(":scope > .campo__rotulo :is(.campo__opcional, .campo__obrigatorio)");
    return marca && (marca.classList.contains("campo__obrigatorio") || normal(marca.textContent || "").includes("emitir"));
  });
}

/** Acende os elementos por alguns segundos (a animação recomeça se clicar de novo). @param {Element[]} alvos @param {string} classe */
function acender(alvos, classe) {
  alvos.forEach((el) => {
    el.classList.remove(classe);
    void (/** @type {HTMLElement} */ (el)).offsetWidth; // reinicia a animação
    el.classList.add(classe);
    window.setTimeout(() => el.classList.remove(classe), DURACAO);
  });
}

/** Espera a rolagem suave terminar (scrollend, com um teto para navegadores sem o evento). */
function aposRolar() {
  return new Promise((resolver) => {
    let feito = false;
    const fim = () => { if (!feito) { feito = true; resolver(undefined); } };
    window.addEventListener("scrollend", fim, { once: true });
    window.setTimeout(fim, 900);
  });
}

document.addEventListener("click", async (evento) => {
  const link = evento.target instanceof Element ? evento.target.closest(".prontidao-documental .checklist__item a[href^='#']") : null;
  if (!(link instanceof HTMLAnchorElement)) return;
  const secao = document.getElementById(link.hash.slice(1));
  if (!secao) return;
  evento.preventDefault();
  const campos = faltando(secao, link.textContent || "");
  const destino = campos[0] || secao;
  const comportamento = calmo() ? "auto" : "smooth";
  destino.scrollIntoView({ behavior: comportamento, block: campos.length ? "center" : "start" });
  history.replaceState(null, "", link.hash);
  if (comportamento === "smooth") await aposRolar();
  if (campos.length) {
    acender(campos, "campo--falta");
    const controle = /** @type {HTMLElement | null} */ (campos[0].querySelector("input:not([type='hidden']), select, textarea, button[role='combobox']"));
    controle?.focus({ preventScroll: true });
  } else {
    acender([secao], "secao--falta");
  }
});
