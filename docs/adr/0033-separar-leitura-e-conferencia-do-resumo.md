# ADR 0033 — Separe leitura e conferência do Resumo

- **Status:** aceito
- **Data:** 2026-10-09

## Contexto

A revisão solicitada para Lista e Resumo identifica um vão artificial entre Motivo e Roteiro. A grade atual coloca esses conteúdos em linhas distintas, compartilhadas com um painel lateral de altura `100cqb`. Diárias usa quatro indicadores de peso semelhante, esticados pela janela. A captura inicial e as medidas ficam em `docs/visual-agents/evidencias/oficios-resumo-lista-refinamento/`.

## Decisão

Agrupar Motivo, Roteiro e Equipe numa coluna de leitura independente, ao lado de uma conferência cuja altura depende do conteúdo. Documentos continuam abrindo a leitura. Diárias ganha uma variante de consulta: total principal, valor individual secundário, destino e composição como metadados. O corpo do modal concentra a rolagem; cabeçalho e ações permanecem fora dele.

A Lista usa fluxo natural de resultados e ações, com filtros temporais tratados como dimensão da busca, sem simular navegação global. Componentes existentes são refinados na origem ou por variante semântica. O Cadastro permanece protegido.

## Alternativas consideradas

Margens negativas esconderiam o sintoma e falhariam com textos longos. Manter a lateral esticada conservaria a competição entre metadados e dados financeiros. Remover informações violaria a cobertura funcional.

## Consequências

Nenhuma alteração de cálculo, autorização, geração ou persistência. Devem ser validados motivos curtos/longos, roteiros de tamanho variável, dados incompletos, documentos em diferentes estados e seis larguras. Capturas, acessibilidade, fluxos de navegador e custo de carregamento comprovam a revisão; a aprovação estética depende da avaliação do usuário.
