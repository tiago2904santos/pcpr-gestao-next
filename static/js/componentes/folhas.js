// @ts-check
/**
 * Folhas de documento empilhadas para ler (termos/visualizar.html): cada <iframe> com a
 * folha HTML (a mesma do PDF) vira uma página inteira, sem barra de rolagem própria.
 *
 *  - a folha é desenhada sempre na largura do A4 (o texto quebra como no PDF) e, numa tela
 *    mais estreita, é reduzida por escala — em vez de espremer e quebrar diferente;
 *  - a altura do quadro acompanha o documento todo (quem rola é a página, não a folha).
 */

const A4_PX = (210 / 25.4) * 96;  // 210 mm em px CSS

/** @param {HTMLIFrameElement} quadro */
function ajustar(quadro) {
  const doc = quadro.contentDocument;
  const caixa = /** @type {HTMLElement | null} */ (quadro.parentElement);
  const pagina = /** @type {HTMLElement | null} */ (caixa?.parentElement ?? null);
  if (!doc || !doc.documentElement || !caixa || !pagina) return;
  doc.documentElement.style.overflow = "hidden";
  // A largura que há é a da página do documento (a moldura acompanha o quadro).
  const disponivel = pagina.clientWidth;
  // Largura natural: a folha A4 mais a margem da mesa (o cinza em volta da folha).
  const natural = Math.max(A4_PX + 48, 0);
  const escala = Math.min(1, disponivel / natural);
  quadro.style.width = `${natural}px`;
  quadro.style.transform = escala < 1 ? `scale(${escala})` : "";
  quadro.style.transformOrigin = "top left";
  const altura = doc.documentElement.scrollHeight;
  quadro.style.height = `${altura}px`;
  // O quadro em escala ocupa menos lugar do que o tamanho declarado: a caixa diz quanto.
  caixa.style.height = `${Math.ceil(altura * escala)}px`;
  caixa.style.width = `${Math.floor(natural * escala)}px`;
}

const quadros = /** @type {HTMLIFrameElement[]} */ (
  Array.from(document.querySelectorAll("iframe[data-folha-inteira]")));
for (const quadro of quadros) {
  quadro.addEventListener("load", () => {
    ajustar(quadro);
    // Fontes e brasão chegam depois do load do HTML: ajusta de novo quando a folha muda.
    const corpo = quadro.contentDocument?.body;
    if (corpo) new ResizeObserver(() => ajustar(quadro)).observe(corpo);
  });
  if (quadro.contentDocument?.readyState === "complete") ajustar(quadro);
}
new ResizeObserver(() => quadros.forEach(ajustar)).observe(document.body);

export {};
