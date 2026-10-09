# ADR 0031 — Compor a preparação inferior do Ofício

- **Status:** aceito para implementação; aprovação estética pendente do usuário
- **Data:** 2026-10-09

## Contexto

O usuário considera Roteiro e seções posteriores inferiores ao Resumo e à parte
superior do Cadastro. Campos e ações fragmentados, bordas repetidas e apresentação
de editor externo prejudicam leitura e composição. Capturas em
`docs/visual-agents/evidencias/oficios-cadastro-inferior/antes/`.

## Decisão

Criar variantes semânticas dos componentes existentes para preparação operacional:
sequência de destinos e mapa integrado, trechos como partidas/resultados, resumo
financeiro compacto e estação documental com prontidão, cópia, editor e histórico.
Manter a estrutura funcional, nomes de campos, ids, atributos de comportamento,
formulários/rotas e aprimoramento progressivo. Não criar nova arquitetura ou biblioteca.
Ativar as variantes no Cadastro e demonstrá-las no UI Lab.

## Alternativas consideradas

Recolorir os mesmos blocos não resolve a hierarquia. Um card por informação
aumenta as camadas. Alterar o fluxo de negócio extrapola o pedido visual.

## Consequências

Header, Identificação e Equipe/transporte preservados. Variantes devem usar tokens,
documentação e estados acessíveis; telas consumidoras de componentes compartilhados
precisam de verificação. Cada bloco exige capturas, crítica e testes antes de avançar.
O gate anterior não valida essa fonte; executar novo gate antes do fechamento.
