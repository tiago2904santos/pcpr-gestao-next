# ADR 0043 — Ofício: a folha do sistema modelo, com colunas iguais

- **Status:** aceito
- **Data:** 2026-10-16

## Contexto

O documento do ofício saía com a estrutura certa (as tabelas de grade do `oficio.docx` de
origem) mas numa folha própria: timbre curto, margens de 9/18/15 mm, o destinatário no corpo
depois da assinatura, "PCPR" escrito no lugar da marca e as colunas das tabelas calculadas
pelo conteúdo — a coluna da saída mais estreita que a da chegada, o transporte com três
colunas de larguras diferentes. O usuário reprovou a assimetria e pediu o modelo do sistema
de gestão de eventos sociais, como já se fez para o diário de bordo e o RT (ADR 0042).

## Decisão

- **A folha do modelo** em `viagens/documentos/oficio.html`: A4 com margens de 4,85 cm em
  cima, 1,27 cm dos lados e 3,4 cm embaixo; o cabeçalho (brasão de 2,4 cm e as três linhas
  do órgão em Arial 10,5 negrito) e o rodapé (o destinatário à esquerda em negrito, a marca
  da PCPR e a linha da unidade em itálico de 7 pt) são elementos corridos do PDF e repetem em
  toda página. O corpo em Times 8, entrelinha 1,3.
- **Colunas iguais**: todas as tabelas com `table-layout: fixed` e sem largura declarada
  por coluna; a grade de 0,75 pt, as células com 3 pt × 6 pt. A equipe sem traço entre um
  servidor e o seguinte; o roteiro de ida e de retorno com uma célula por coluna e uma linha
  por trecho; o transporte com três colunas iguais, alinhadas ao meio.
- **Os textos do modelo**: abertura "Senhor Delegado, através deste, solicito … e medidas para
  a concessão de diárias e recursos para combustível, conforme cronograma abaixo:", a
  declaração do cartão corporativo por extenso, "Respeitosamente," e a chefia em 9 pt.
- **Caber numa página**: `documentos/pdf.py` refaz o PDF com `doc-compacto-1` e `-2` no
  `<body>` enquanto passar de uma página (primeiro os espaços, depois a letra); a contagem
  de páginas do editor usa o mesmo laço, para dizer o que o arquivo terá.
- **Nº da solicitação**: a coluna "Nº solicitação (Central de Viagens)" sai preenchida com o
  número gravado na prestação de contas quando ele já existe (retificação/nova versão).
- **Na tela** (folha do editor), o cabeçalho e o rodapé ocupam as mesmas faixas das margens
  de impressão e o rodapé fecha o pé do papel; o papel segue contínuo quando o texto cresce.
- **DOCX**: o rodapé composto (destinatário, marca, unidade) vai para o rodapé da seção.

As regiões do editor continuam `cabecalho`, `corpo` e `rodape` (a assinatura); o
destinatário e a linha da unidade vêm da configuração e não se editam na folha. Uma edição
antiga da região `rodape` aparece como desatualizada, como qualquer mudança de modelo.

## Consequências

- Ofício, folha do editor, DOCX e contagem de páginas saem de um modelo só.
- O que o modelo não tem (roteiro por trechos com volta intermediária, D7) segue na mesma
  grade, com três colunas (a do número estreita).
