# ADR 0037 — Disparar o deploy do main pelo GitHub Actions

- **Status:** aceito
- **Data:** 2026-10-14

## Contexto

O usuário pediu publicação imediata após push no main. A VPS já executa o PREVIEW
por Compose, com snapshots sem Git, Nginx e volumes existentes. O fluxo de produção
do ADR 0035 não está configurado nessa instância. Evidências da atualização manual:
`docs/ops/vps-main-20261014.md`.

## Decisão

Workflow independente em `push: main`, concorrência sem cancelar a troca em curso.
CI continua paralelo. Chave exclusiva, com `restrict` e comando forçado no SSH,
aceita somente `deploy <SHA>`. O executor instalado por administração na VPS
valida o SHA contra o main público, faz sparse checkout apenas do contexto de
runtime e publica imagem imutável. Não usa comandos enviados pelo cliente como shell.
Script instalado não é substituído automaticamente por conteúdo futuro do repo.

Preservar arquitetura/segredos/volumes da instância existente. Backup consistente,
checks e saúde fazem parte do deploy rápido. Migração automática apenas no banco
PREVIEW esperado; nunca reset/seed. Reversão automática só sem tentativa de migração.
Logs, travamento por flock, descarte de SHA obsoleto, disco mínimo e idempotência.

## Alternativas consideradas

- Timer de polling: acrescenta atraso e consultas sem necessidade.
- Esperar CI inteiro: contraria o pedido explícito de publicação imediata.
- Chave SSH administrativa irrestrita no GitHub: privilégio desnecessário.
- Migrar a infraestrutura inteira para produção: fora do escopo solicitado.

## Consequências

Todo push no main inicia o deploy sem aprovação adicional. Build/checks/backup
ainda levam tempo; push não implica que uma versão já esteja saudável no ar.
A instância única pode ter breve indisponibilidade durante backup e troca.
Backups são preservados; falta de espaço ou falha exige ação administrativa.
Regras de produção continuam separadas; mudar para dados reais bloqueia o executor.

Referências primárias:
[GitHub — deploy e concorrência](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments),
[OpenSSH — restrict, command e SSH_ORIGINAL_COMMAND](https://man.openbsd.org/sshd).
