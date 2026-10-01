# ADR 0013 — Overdrive 2: linguagem de componentes, foco próprio e motion 2.0

- **Status:** aceito · **Data:** 2026-10-01

## Contexto
O redesign Overdrive (ADR 0012) deu identidade visual ao produto. Os componentes, porém,
ainda seguiam padrões genéricos: foco azul do navegador, status só por cor, formulário em
cartões empilhados com índice lateral, detalhe com painel lateral, lista sem contexto.
O dono do produto pediu componentes "desenhados para este produto", uma linguagem de
interação própria, menos caixas e nenhum painel lateral flutuante.

## Decisão
1. **Foco próprio** (`--foco-*`): anel grafite + halo claro; dourado sobre superfícies
   escuras; campos acendem. Testado por estilo computado no Chromium.
2. **Linguagem de estado pela forma**: anel vazio / ✓ / × / pulso, nos selos, no trilho
   de processo, no progresso e nas seções.
3. **Linguagem de ação**: `aria-busy` → `data-estado="concluido|erro"` por
   `acao.js`; salvamento confirma na barra (sem toast).
4. **Documento em vez de cartões**: `.documento > .secao` no detalhe e na edição; histórico
   abaixo, em colunas, com disclosure; próximos passos na composição principal.
   **Nenhum painel lateral.**
5. **Progresso horizontal** (`nav.progresso` + `<progress>`) substitui o índice lateral.
6. **Lista**: grupos por mês presos sob o topo; expansão em linha com fragmento HTMX
   (`viagens:resumo`, mesma política de visibilidade); placa visível no celular.
7. **Motion 2.0**: View Transitions entre páginas e nas trocas HTMX, com nomes em
   `data-vt` via `attr()` tipado (sem estilos inline). Reduced-motion desliga tudo.
8. **Caixa e rádio desenhados no DS** (`appearance: none`, inputs nativos).
9. Três conceitos por componente central ficam no UI Lab (seção 11) e em
   `docs/design-system/explorations.md`.

## Consequências
- O arquétipo `layout-detalhe` deixa de ser usado pelo ofício; `layout-formulario` idem.
- Testes: foco (unitário + e2e), expansão da lista (e2e), `resumo` (visibilidade),
  barra "salvo" (sem toast); os e2e que esperavam o toast de salvamento passaram a
  verificar a barra.
- Navegadores sem View Transitions ou sem `attr()` tipado (Firefox/Safari atuais)
  recebem trocas instantâneas: nada quebra, só não anima.
- Orçamentos de desempenho: +2 módulos JS pequenos (`acao.js`, `registro.js`), sem
  bibliotecas; CSS cresce ~9 KB antes de compressão.
