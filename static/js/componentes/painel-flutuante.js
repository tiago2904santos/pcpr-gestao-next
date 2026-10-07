// @ts-check
/**
 * Painel que precisa sair de dentro de um <dialog>.
 *
 * Um <dialog> rola e recorta o que passa das suas bordas: a lista de uma escolha aberta
 * perto do pé da janela nascia cortada (ou empurrava uma barra de rolagem). Dentro de um
 * diálogo, o painel vira **popover**, que o navegador pinta na camada de topo — acima da
 * janela e sem recorte — com a posição calculada aqui, já que ele deixa de seguir o campo.
 *
 * O mesmo vale para qualquer contêiner marcado com `data-camada-topo` — a folha inferior
 * de filtros do celular rola e recortava o calendário e a lista de "Veículo" (QA Lote 2,
 * B1). Enquanto o painel está solto, rolar o contêiner o leva junto.
 *
 * Fora disso nada muda: o painel continua posicionado pelo CSS, junto do campo.
 */

const CAMADA = "dialog[open], [data-camada-topo]";

/** @param {HTMLElement} painel */
function suportado(painel) {
  return typeof (/** @type {any} */ (painel).showPopover) === "function";
}

/**
 * Põe o painel na camada de topo, alinhado ao campo. Sem diálogo aberto em volta, não faz
 * nada. @param {HTMLElement} painel @param {HTMLElement} ancora
 */
export function soltar(painel, ancora) {
  if (!ancora.closest(CAMADA) || !suportado(painel)) return;
  if (!painel.hasAttribute("popover")) painel.setAttribute("popover", "manual");
  try {
    /** @type {any} */ (painel).showPopover();
  } catch {
    return; // já aberto (ou o navegador recusou): a posição abaixo ainda vale
  }
  posicionar(painel, ancora);
  const acompanhar = () => posicionar(painel, ancora);
  window.addEventListener("scroll", acompanhar, true);
  window.addEventListener("resize", acompanhar);
  /** @type {any} */ (painel).__acompanhar = acompanhar;
}

/** Recoloca o painel junto do campo (rolagem, mudança de tamanho).
 * @param {HTMLElement} painel @param {HTMLElement} ancora */
export function posicionar(painel, ancora) {
  if (!painel.matches(":popover-open")) return;
  const campo = ancora.getBoundingClientRect();
  const folga = 4;
  painel.style.position = "fixed";
  // Calendário/relógio: logo abaixo do botão, alinhado à direita dele; listas: na largura do campo.
  const botao = painel.classList.contains("seletor__painel")
    ? ancora.querySelector(".seletor__botao") : null;
  if (botao) {
    const direita = botao.getBoundingClientRect().right;
    painel.style.left = `${Math.max(8, direita - painel.offsetWidth)}px`;
    painel.style.right = "auto";
  } else {
    painel.style.left = `${campo.left}px`;
    painel.style.width = `${campo.width}px`;
  }
  // Abre para baixo; se não couber e couber acima, abre para cima (como fora do diálogo).
  const altura = painel.offsetHeight;
  const abaixo = campo.bottom + folga;
  if (abaixo + altura <= window.innerHeight - folga || campo.top - altura - folga < folga) {
    painel.style.top = `${abaixo}px`;
    painel.style.bottom = "auto";
  } else {
    painel.style.top = "auto";
    painel.style.bottom = `${window.innerHeight - campo.top + folga}px`;
  }
}

/** Devolve o painel ao fluxo do campo. @param {HTMLElement} painel */
export function recolher(painel) {
  if (!painel.hasAttribute("popover")) return;
  const acompanhar = /** @type {any} */ (painel).__acompanhar;
  if (acompanhar) {
    window.removeEventListener("scroll", acompanhar, true);
    window.removeEventListener("resize", acompanhar);
    delete (/** @type {any} */ (painel).__acompanhar);
  }
  if (painel.matches(":popover-open")) {
    try {
      /** @type {any} */ (painel).hidePopover();
    } catch { /* já fechado */ }
  }
  painel.removeAttribute("popover");
  painel.style.position = painel.style.left = painel.style.top = painel.style.right = "";
  painel.style.bottom = painel.style.width = "";
}
