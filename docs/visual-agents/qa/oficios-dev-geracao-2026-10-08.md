# DEV local — Resumo atualizando continuamente

Em 08/10/2026, o usuário informou atualizações contínuas em
`http://127.0.0.1:8000/viagens/oficios/`.

## Diagnóstico e recuperação

- O Resumo consultava a geração documental a cada 2–3 segundos. A observação
  inicial registrou 66 consultas ao mesmo endpoint; não havia erro no console.
- A leitura do banco DEV local mostrou dois documentos em `gerando`, mensagens
  de geração pendentes desde 14h34 e zero tentativas. Não havia worker ativo.
- Foi iniciado o comando existente `processar_outbox`, intervalo de 5 segundos,
  com o runtime GTK já instalado. Antes do início, o wrapper confirmou ambiente
  DEV, PostgreSQL `127.0.0.1:5432`, banco local, SMTP desabilitado e eProtocolo
  simulado. Não foram alterados dados manualmente, regras ou snapshots da emissão.
- Às 16h27, os dois documentos passaram a `pronto`; a fila pendente ficou vazia.
- O navegador mostrou os dois links PDF, nenhum texto de geração e zero elementos
  `[data-resumo-poll]`. Uma observação posterior registrou apenas uma consulta ao
  Resumo nos 265 segundos de vida da página, a última aos 6,34 segundos.

O worker ficou ativo para as próximas emissões. O processo supervisor iniciado
foi 26704; logs locais ignorados: `var/worker-geracao-dev.log` e
`var/worker-geracao-dev-erro.log`. Reiniciar o computador encerra esse processo;
o DEV precisa iniciar servidor e worker em conjunto.

## Classificação e limites

Problema operacional do ambiente: worker ausente, sem regressão de código
demonstrada. A atualização automática terminou normalmente quando a geração foi
processada. Nenhuma captura com dados do usuário foi adicionada ao repositório.
O problema da ferramenta **Anotar do Codex** permanece separado e não foi
resolvido por esta recuperação.
