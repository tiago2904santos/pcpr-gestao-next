// @ts-check
/**
 * Barra de ações que acompanha a rolagem (.barra-acoes--registro e a das listas, .barra-acoes--colecao): marca `data-grudada` enquanto ela
 * está presa à borda de baixo da tela. Presa, encosta na borda e só arredonda os cantos de cima;
 * no seu lugar, ao fim do conteúdo, volta a ser um cartão com os quatro cantos arredondados (CSS).
 * O observador olha 1px além da borda: presa, a barra nunca fica 100% dentro dessa área.
 */

// Sem IntersectionObserver (navegador antigo): a barra fica como cartão, sem `data-grudada`.
const observador = "IntersectionObserver" in window ? new IntersectionObserver((entradas) => {
  for (const entrada of entradas) {
    entrada.target.toggleAttribute("data-grudada", entrada.intersectionRatio < 1);
  }
}, { threshold: [1], rootMargin: "0px 0px -1px 0px" }) : null;

/** @type {WeakSet<Element>} */
const observadas = new WeakSet();

function observar() {
  if (!observador) return;
  for (const barra of document.querySelectorAll(".barra-acoes--registro, .barra-acoes--colecao")) {
    if (observadas.has(barra)) continue;
    observadas.add(barra);
    observador.observe(barra);
  }
}

observar();
document.addEventListener("htmx:afterSettle", observar);

export {};
