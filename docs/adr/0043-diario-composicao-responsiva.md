# 0043 — Diário de bordo como preparação responsiva de documento

- Data: 2026-10-16
- Estado: revisão inicial rejeitada; substituída pela decisão abaixo

## Contexto

O usuário rejeitou a apresentação do diário, exceto o editor. A tabela larga,
os recursos empilhados e a repetição de textos dificultam o preenchimento.
O parcial de horários ainda contém atributos órfãos e título duplicado.

## Decisão

Derivar de DOCUMENT, sobrescrevendo a composição para manter o editor em largura
inteira. Reusar seções em cartões, resumo de recursos em grade e as linhas de
hodômetro já presentes no Design System. Não adicionar CSS nem componente visual.
Os horários permanecem um ajuste explícito em divulgação nativa, sem mudar o ofício.
Preservar integralmente o bloco funcional do editor, inclusive seus atributos.
Generalizar o seletor de sugestões de `tr[data-prevista]` para `[data-prevista]`.

## Consequências

### Revisão por pedido explícito do usuário

Usar FORM com composição sobrescrita (há formulários independentes, sem aninhar),
exatamente como a preparação de Ofício: `documento--preparacao`, seções numeradas,
`secao__conteudo`, campos de recursos abertos, roteiro e documento. Remover cartões
e etapas. O editor permanece byte a byte; nenhum serviço ou regra muda.
Evidências desta revisão: `docs/qa/diario-base-oficio-20261016.md`.

Os campos deixam de depender de tabela e recebem rótulos visíveis. Autosave e
valores continuam no serviço atual. Os testes cobrem sugestões sem sobrescrita,
foco, navegação, viatura, horários, consulta e travas. As demais folhas não mudam.
Evidências e limites serão registrados em `docs/qa/diario-refino-20261016.md`.
