// @ts-check
/**
 * Ícone do sprite para os componentes que se montam no navegador. O caminho sai de um
 * ícone que a página já desenhou, então vale o mesmo arquivo (com o hash do static) —
 * sem repetir a URL em JavaScript.
 *
 * @param {string} nome nome do ícone no sprite, sem o prefixo "i-"
 * @param {string} [classe]
 */
export function icone(nome, classe = "icone") {
  const uso = document.querySelector("svg.icone use")?.getAttribute("href") || "";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", classe);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `${uso.split("#")[0]}#i-${nome}`);
  svg.append(use);
  return svg;
}
