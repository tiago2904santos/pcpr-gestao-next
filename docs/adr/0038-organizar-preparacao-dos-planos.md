# ADR 0038 — Organizar a preparação dos planos em etapas de trabalho

- **Status:** aceito
- **Data:** 2026-10-15

## Contexto

O usuário pediu o refinamento de Planos no padrão de Ofícios, Roteiros, Termos e
OS. A captura da preparação concentra efetivo, deslocamento e diárias dentro de
Identificação, enquanto eventos adicionais aparecem no bloco documental. Evidência:
`../visual-agents/evidencias/planos-refino-20261015/antes/`.

## Decisão

Recompor a preparação com componentes existentes, na ordem Identificação,
Efetivo e diárias, Atividades, Eventos adicionais e Documento. Manter as âncoras
atuais e usar o índice compacto de preparação, sem inventar progresso financeiro
ou estado de completude. Aplicar ajustes de composição em CSS exclusivo de Planos,
preservando as alterações locais dos componentes compartilhados.

## Alternativas consideradas

- Somente mudar espaçamentos: não resolve a concentração de tarefas na primeira seção.
- Assistente em várias páginas: fragmenta autosave e dificulta conferência conjunta.
- Alterar os componentes globais: amplia a regressão para módulos fora do pedido.

## Consequências

O operador encontra cálculo e eventos por etapas nomeadas; não há mudança nas
regras ou no documento oficial. Eventos continuam com formulário externo.
Novas composições devem ser verificadas em 360 e 1440 px e nos fluxos de autosave,
validação, multievento e geração.
