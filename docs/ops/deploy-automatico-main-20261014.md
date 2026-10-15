# Ativação do deploy automático — 14/10/2026

## Observar / entender

Usuário pediu publicação imediata a cada mudança do main. Diagnóstico somente
leitura repetido na VPS antes da configuração. Instância segue PREVIEW sintético,
com dados/volumes/Nginx existentes. Main avançou para `303aab8`; incorporado por
fast-forward, sem remover alterações de outros autores. A versão ainda no ar era
`8757f24`. Evidência da implantação anterior: `vps-main-20261014.md`.

## Projetar / implementar

Regra registrada primeiro em `docs/product/deploy-automatico-main.md`, ADR 0037.
Workflow separado em push/main, sem depender do CI longo, com concorrência que
não cancela uma troca em andamento. Executor root estático, chave exclusiva
restrita a `deploy <SHA>`, host key fixada e segredo guardado no GitHub Actions.
Repositório público acessado por HTTPS sem token na VPS. Nenhum segredo no Git.

Executor instalado em `/usr/local/lib/pcpr-main/`; cache/logs/backups em
`/srv/pcpr/automatico`. Build sem segredos no contexto; depois copia a configuração
privada existente. Ambiente/banco diferente do PREVIEW esperado é recusado.
Check, backup consistente validado, migrações com serviços parados, saúde, worker
e registro de SHA. Reversão de código só sem tentativa de migração; após tentativa,
falha exige intervenção, sem restaurar dados automaticamente. Sem seed/reset.

## Testar / comparar / criticar / corrigir

- Testes de política: SHA, comandos com sufixos/injeção, produção e banco remoto
  recusados; configuração esperada aceita.
- Bash syntax, ShellCheck 0.11.0 e Actionlint 1.7.7 passaram. Workflow YAML
  conferido: push somente main, cancel-in-progress=false. Lint em contêineres sem
  rede e com fonte somente leitura.
- Chave real: autenticou e recusou `id` com saída 64. Uma ausência de newline no
  authorized_keys preexistente foi corrigida inserindo apenas a separação da nova
  linha; as duas chaves anteriores e seus comentários foram preservados.
- Chamada real com SHA antigo `8757f24`: descartada contra main `303aab8` em
  15/10/2026 01:34 UTC; aplicação não reiniciada, nenhum dado alterado.
- Secret e três variables do GitHub confirmados por nomes, sem mostrar valores
  privados. Chave temporária fora do OneDrive; não será mantida após a validação.

## Validar a ativação

A publicação deste commit deve disparar a primeira execução de **Publicar main
na VPS**. O resultado será comparado ao SHA em `/srv/pcpr/app/versao-main.txt`,
à saúde HTTPS e à página publicada. Não foi repetida a suíte inteira do produto:
mudança de infraestrutura, CI paralelo e validações específicas acima.
