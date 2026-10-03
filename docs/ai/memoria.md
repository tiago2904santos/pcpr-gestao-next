# Memória e contexto do agente operacional

Não colocar tudo no prompt. O contexto é montado sob demanda a partir de cinco fontes:

| Fonte | O que dá | Como |
|---|---|---|
| Conhecimento de domínio | regras (diárias, prazos, assunto, numeração), glossário, fluxos | `docs/product/` + docstrings do domínio, indexados para busca; versão fixada por release |
| Banco | estado atual (ofício, equipe, roteiro, documentos, pendências) | **só por ferramentas de leitura** com política |
| Recuperação (retrieval) | ofícios/roteiros semelhantes, textos prontos, decisões anteriores | busca textual no PostgreSQL primeiro (`pg_trgm`/full-text); vetores só se a busca textual não bastar |
| Chamadas de ferramenta | dados frescos de integrações (protocolo) | ferramentas de integração |
| Histórico/auditoria | o que já foi feito, por quem, o que foi aprovado/negado | `Historico`, `ExecucaoFerramenta`, `PedidoAprovacao` |

## Contexto operacional cruzado

O agente precisa ver que Ofício ↔ Roteiro ↔ Diárias ↔ Plano de Trabalho ↔ Termo ↔ Ordem de
Serviço ↔ Justificativa ↔ eProtocolo ↔ Prestação são **um processo**. No modelo de domínio
isso vira a entidade agregadora **Viagem** (módulo 8 do roadmap) — as ferramentas de leitura
devem aceitar "a viagem X" e devolver todas as peças ligadas.

## Memória de conversa

Por usuário e por tarefa (não global); expira; nunca guarda segredo nem dado pessoal além do
necessário à tarefa; o usuário pode ver e apagar.
