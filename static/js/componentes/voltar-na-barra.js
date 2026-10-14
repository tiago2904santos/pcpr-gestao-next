// @ts-check
/**
 * "Voltar para …" (a tarefa que ficou aberta em outra tela) vai para a barra de ações da página, à esquerda,
 * quando ela tem uma: o atalho de saída fica junto das outras ações em vez de flutuar sobre o conteúdo.
 * Sem barra, ele continua flutuando no canto (CSS). Sem JavaScript, idem.
 */

const botao = document.querySelector("a.voltar-tarefa");
const barra = document.querySelector("main .barra-acoes:not(.barra-acoes--preparacao)");

if (botao && barra) {
  botao.classList.add("voltar-tarefa--na-barra", "botao--texto");
  barra.prepend(botao);
}

export {};
