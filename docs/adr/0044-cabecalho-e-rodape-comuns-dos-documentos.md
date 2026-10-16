# ADR 0044 — Cabeçalho, rodapé e margens comuns a todos os documentos

- **Status:** aceito
- **Data:** 2026-10-16

## Contexto

Cada modelo de documento (ofício, justificativa, termo, OS, plano de trabalho, relatório
técnico, diário de bordo) trazia a sua própria folha: margens de 9 a 48 mm em cima, brasão de
13 a 28 mm, linhas do órgão em Times ou Arial de 7,5 a 12 pt, rodapé ora "PCPR" escrito, ora a
marca, e o diário sem rodapé. O usuário pediu um padrão só, com margens menores (sobretudo as
verticais) e o brasão pequeno.

## Decisão

- **Uma folha comum**, `viagens/documentos/_folha.html`, incluída no `<style>` de cada modelo
  antes das regras próprias dele: as fontes (Liberation Serif/Sans como "Doc Serif"/"Doc
  Sans"), a página A4 com **32 mm em cima, 15 mm dos lados e 18 mm embaixo**, o cabeçalho e o
  rodapé como elementos corridos do PDF (repetem em toda página), a marca d'água da minuta e,
  na folha de tela, as mesmas faixas no topo e no pé do papel. Parâmetros: `margem_inferior`
  (o ofício usa 34 mm, para o destinatário no rodapé) e `paisagem` (o diário).
- **Um cabeçalho**, `_timbre.html`: brasão de 13 mm e as três linhas do órgão em Arial 9,5
  negrito, caixa alta. **Um rodapé**, `_rodape.html`: a marca da PCPR (5 mm) e a linha da
  unidade em itálico 7 pt; o ofício põe o destinatário acima, à esquerda. O rodapé vem
  primeiro no `<body>`: elemento corrido vale desde a primeira página; na tela vai para o pé.
- O corpo de cada documento (letra, tabelas, blocos, regiões do editor) não muda. O
  relatório técnico perde a folha ASCOM (brasão de 28 mm, 12 pt) e o diário ganha o rodapé.

## Consequências

- Os sete documentos saem com a mesma geometria; uma mudança institucional (brasão, marca,
  linhas do órgão) é feita num lugar.
- O plano de trabalho mantém o número da página (`@bottom-right`) além do rodapé comum.
