# ADR 0014 — Campos no estilo do modelo e seletores próprios (data, hora, lista)

- **Status:** aceito · **Data:** 2026-10-02
- **Substitui em parte:** ADR 0007 (linha "Seletor de data/hora: `input type=date/time` nativo")

## Contexto
O dono do produto pediu componentes "mais parecidos com os do modelo" (o sistema de
referência) e apontou que calendário, relógio e listas suspensas ainda usavam o visual
nativo do navegador, fora da identidade do sistema. No modelo, o nome do campo fica sobre a
linha de cima de uma caixa branca, e data e hora dos trechos ficam lado a lado.

## Decisão
1. **Campo com rótulo na borda**: caixa branca com borda; o rótulo fica sobre a linha de
   cima (`.campo > .campo__rotulo` posicionado). O fundo do rótulo usa duas variáveis
   locais (`--fundo-rotulo`, `--fundo-entrada`) para servir sobre a folha branca e sobre
   faixas cinzas. A identidade continua no foco (borda grafite + halo dourado). O conceito
   "campo aceso" (tingido em repouso) vira registro no UI Lab.
2. **`<pc-data>`**: texto dd/mm/aaaa com máscara + calendário próprio no padrão
   "Date Picker Dialog" do WAI-ARIA APG (grade com setas, Home/End, PageUp/PageDown, Shift
   para ano, Enter escolhe, Esc fecha e devolve o foco ao botão).
3. **`<pc-hora>`**: texto hh:mm com máscara + relógio em duas listas (horas; minutos de 5
   em 5). Minutos fora do passo continuam digitáveis.
4. **`<pc-select>`**: botão `role="combobox"` + `listbox` sobre o `<select>` comum
   (padrão "Select-Only Combobox" do APG, com salto por letra). O `<select>` continua
   sendo o valor do formulário.
5. **Data + hora** (`EntradaDataHora`): dois campos (`nome_0`, `nome_1`) que chegam ao
   servidor como "dd/mm/aaaa hh:mm"; o envio antigo num campo só (`aaaa-mm-ddThh:mm`)
   continua aceito.
6. Sem JavaScript, os três viram campos de texto e `<select>` comuns: nada depende do
   script para funcionar. Os painéis abrem sempre para baixo (acima ficariam sob a faixa
   fixa do topo) e a página rola o bastante para não ficarem sob a barra de ações.

## Consequências
- +~14 KB de JS bruto (~4 KB comprimido). Orçamento de JS revisto em
  `docs/quality/performance-budgets.md`.
- Testes de navegador escolhem campos de data pelo papel (`textbox`) e com nome exato,
  porque o botão do calendário também cita o nome do campo.
- O seletor nativo do celular (rolos de data/hora) deixa de aparecer; o teclado numérico
  continua (`inputmode="numeric"`).
