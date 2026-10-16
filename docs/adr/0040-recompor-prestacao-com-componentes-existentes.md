# ADR 0040 — Recompor a prestação com os componentes existentes

- **Status:** aceito
- **Data:** 2026-10-15

## Contexto

O usuário pede substituir a interface inteira de Prestação sem inventar novos
componentes. Observação e contratos em `docs/product/prestacao-refinamento-integrado.md`;
capturas anteriores em `docs/visual-agents/evidencias/prestacao-refino-20261015/antes/`.
Lista, Diário, Relatório e Documentos compartilham as mesmas regras e equipe.

## Decisão

Recompor os templates com cartao, registro, pessoa/avatar, abas, grade,
divulgacao e blocos já existentes. Reutilizar o resumo real do Ofício, em vez
de criar resumo, endpoint ou editor paralelo. Não adicionar CSS/JavaScript.
Preservar os formulários separados, hooks e políticas atuais.

## Alternativas consideradas

Uma nova folha de estilos manteria duas linguagens e contraria o pedido.
Uma prestação nova manual mudaria o domínio e duplicaria o Ofício.
Apagar regras, dados ou documentos não é necessário para substituir a interface.

## Consequências

A consistência vem da composição dos componentes atuais. As mesmas ações e
validações devem funcionar após a troca. Bases antigas com uso no UI Lab ou
em outras telas não serão removidas sem prova de ausência de consumidores.
