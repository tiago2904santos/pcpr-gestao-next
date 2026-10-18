# ADR 0044 — Unificar atividades e serviços com identidade local estável

- **Status:** aceito
- **Data:** 2026-10-17

## Contexto
AtividadePlano possui código, meta e recurso e é referenciada por planos, eventos do
plano, resultados e conjuntos. Eventos.Servico possui nome e situação e é referenciado
por solicitações e modelos de tipos de evento. A decisão explícita de produto define
que ambos representam o mesmo cadastro. Igualdade de nome não comprova identidade.

## Decisão
Preservar a tabela e os IDs de AtividadePlano como catálogo canônico; manter Servico
como proxy contextual sem cópia de dados e sem mudança das permissões das rotas.
Migrar relações por colunas temporárias, preservando serviços legados e o mapa de
origem/destino e relações para recuperação. O único merge automático é CIN, identificado
por código e conteúdo integral da carga do plano e nome/situação da carga de eventos.
Nome canônico permanece o do plano. Outros homônimos ficam separados e registrados.

Concentrar leitura de entidades compartilhadas em uma fonte local. A fonte externa
futura atualiza um espelho local por um vínculo de identidade (fonte, tipo, ID externo)
único; consumidores continuam usando IDs locais e validações locais. Implementar
comparação de três estados (base externa, atual local, recebido), recusa de conflitos e
campos externos explicitamente autorizados. Nenhuma rede é conectada nesta etapa.

## Alternativas consideradas
- Nova tabela canônica com troca de todos os IDs: amplia desnecessariamente migração
  e risco em planos/resultados existentes.
- Copiar serviços entre módulos: perpetua identidades independentes.
- Deduplicar por nome: pode fundir registros distintos e perder histórico.
- Banco remoto direto nos formulários: espalha detalhes de transporte e fragiliza FKs.

## Consequências
Nome técnico AtividadePlano permanece por compatibilidade; o nome público é comum.
Migração guarda legado para auditoria e recuperação, sem consumidores operacionais.
A recuperação é explícita por mapa; reverter esquema depois de novos usos requer
reconciliação, portanto a migração não oferece rollback automático destrutivo.
Campos de relação e configuração continuam locais até contrato específico da origem.
