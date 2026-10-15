# ADR 0039 — Priorizar documentos no hub de Viagens

- **Status:** aceito
- **Data:** 2026-10-15

## Contexto

O usuário solicitou um refinamento profundo do módulo. Nas capturas da viagem 1,
dezenas de vínculos existentes aparecem antes dos documentos já usados, aumentando
o percurso até a tarefa principal. Evidência em `visual-agents/evidencias/viagens-refino-20261015/antes/`.

## Decisão

Antecipar Documentos após Dados; recolher o reaproveitamento de documentos e
agrupar a conferência por etapa real. A região documental pode ficar dentro do
formulário de dados porque suas ações de criação têm `form` externo explícito;
não introduzir formulários aninhados. A conferência com seu formulário próprio
continua fora de `form-viagem`. Manter ordem visual e DOM coincidentes.

## Alternativas consideradas

- Somente espaçamentos: mantém a lista de vínculos dominando o trabalho.
- Reordenar só com CSS: divergência entre navegação por teclado e leitura visual.
- Novo assistente por etapas: fragmenta o hub e altera o contrato de autosave.

## Consequências

Sem mudança de regra ou API. IDs das regiões vivas e formulários são contratos de
regressão. Busca de vínculos é apenas local aos candidatos renderizados, não uma
consulta remota. CSS específico evita regressões nos módulos em edição paralela.
