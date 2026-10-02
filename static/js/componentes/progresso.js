// @ts-check
/**
 * Faixa de progresso do formulário longo (`nav.progresso--fixo`):
 *  - "você está aqui": marca a etapa da seção que ocupa o alto da tela
 *    (`.progresso__etapa--atual` + `aria-current="location"` no link);
 *  - quando a faixa descola do conteúdo e passa a flutuar sob o topo, ganha sombra.
 * Só IntersectionObserver: nada roda no scroll.
 */
const faixa = /** @type {HTMLElement | null} */ (document.querySelector(".progresso--fixo"));

if (faixa) {
  const links = /** @type {HTMLAnchorElement[]} */ (Array.from(faixa.querySelectorAll(".progresso__etapa > a")));
  const secoes = links
    .map((a) => document.getElementById(decodeURIComponent(a.hash.slice(1))))
    .filter((s) => s !== null);

  /** @param {string} id */
  const marcar = (id) => {
    links.forEach((a) => {
      const atual = a.hash === `#${id}`;
      a.parentElement?.classList.toggle("progresso__etapa--atual", atual);
      if (atual) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    });
  };

  // A seção "atual" é a que cruza uma linha logo abaixo da faixa.
  const visiveis = new Map();
  const espia = new IntersectionObserver((entradas) => {
    entradas.forEach((e) => visiveis.set(e.target.id, e.isIntersecting));
    const primeira = secoes.find((s) => visiveis.get(/** @type {HTMLElement} */ (s).id));
    if (primeira) marcar(/** @type {HTMLElement} */ (primeira).id);
  }, { rootMargin: "-30% 0px -60% 0px" });
  secoes.forEach((s) => espia.observe(/** @type {HTMLElement} */ (s)));

  // Sentinela logo acima da faixa: quando sai da tela, a faixa está flutuando.
  const sentinela = document.createElement("div");
  sentinela.setAttribute("aria-hidden", "true");
  faixa.before(sentinela);
  const topo = document.querySelector(".topo");
  const alturaTopo = topo ? Math.round(topo.getBoundingClientRect().height) : 0;
  new IntersectionObserver(([e]) => {
    faixa.classList.toggle("progresso--flutuando", !e.isIntersecting);
  }, { rootMargin: `-${alturaTopo + 1}px 0px 0px 0px` }).observe(sentinela);
}

// Sem exportações: a marca de módulo permite o import() sob demanda (app.js).
export {};
