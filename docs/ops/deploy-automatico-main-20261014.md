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

### Resultado da execução real

Commit de configuração: `e0e945ee1f41b06ddaaa5deab44f5a86b9f84771`.
O push disparou automaticamente o workflow
[38666563836](https://github.com/tiago2904santos/pcpr-gestao-next/actions/runs/38666563836),
que concluiu com **success em 2min17s**, sem comando manual de atualização na VPS.
Histórico do servidor: publicação concluída em 15/10/2026 01:38:46 UTC.

Em resposta à dúvida do usuário sobre merges pelo GitHub, conferidos separadamente:
API `commits/main` do GitHub, `FETCH_HEAD` da VPS e `versao-main.txt` ativo:
os três apontaram para `e0e945ee1f41b06ddaaa5deab44f5a86b9f84771`.
Origem do cache da VPS: `https://github.com/tiago2904santos/pcpr-gestao-next.git`.
O merge anterior `303aab8` está incluído nesse commit; não há leitura do repositório
da estação Windows. A diferença temporária era o build/troca em andamento, não
dependência do main local. Merges na interface GitHub também geram push no main.

Web saudável e worker executando a imagem `pcpr-gestao:vps-e0e945ee...`; contêiner
de banco preservado. Login DEMO e resumo da OS #2 conferidos no HTTPS publicado,
zero erros JS e nenhum cadastro gravado. Captura em 1440 × 900:
`../visual-agents/evidencias/deploy-automatico-20261014/1440/resumo-os-vps-main-github.png`.
Credencial privada temporária removida da estação após o teste; permanece apenas
no GitHub Secret para o workflow. Nenhuma outra chave SSH foi revogada/alterada.
Evidência final e captura registradas localmente, sem outro push só para testes.
