# ADR 0032 — Refinar percurso e estação documental

- **Status:** aceito para implementação; aprovação estética pendente
- **Data:** 2026-10-09

## Contexto

O novo pedido exige reconstrução da metade inferior da Folha e preservação da
parte superior. A composição de 0031 mantém busca larga, mapa elástico e grupos
com peso semelhante. Baseline atual registrada em
`docs/visual-agents/evidencias/oficios-cadastro-inferior-r2/antes/`.

## Decisão

Refinar as variantes existentes: recurso de roteiro integrado, sequência de
pontos e mapa proporcional com legenda própria, partidas e chegadas distintas,
conferência compacta, contexto de justificativa, estação documental e log.
Todas as alterações de apresentação preservam ids, campos, nomes, ações,
autosave e contratos. Sem biblioteca nova, alteração de domínio, arquivo oficial,
permissão, integração ou dados históricos.

## Alternativas consideradas

Recolorir a estrutura atual preservaria a fragmentação. Mais cartões aumentariam
camadas. Um novo editor mudaria arquitetura e confiabilidade sem necessidade.

## Consequências

Variantes compartilhadas demonstradas no UI Lab. Antes/depois em cinco larguras,
segunda crítica e testes por bloco, seguidos de gate integral. Estado visual é
candidato; o fechamento anterior permanece histórico. Alterações locais do usuário
não serão descartadas ou incluídas indiscriminadamente em commit.
