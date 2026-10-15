# Deploy automático do main — PREVIEW da VPS

Todo push no main inicia `.github/workflows/deploy-vps.yml`, independente do CI.
Não publica branches, PRs nem alterações locais. Há também execução manual do
workflow pela aba Actions, selecionando main. Uma publicação em andamento não é
cancelada por outra; versão obsoleta não substitui a ponta atual do main.

## Configuração instalada

- VPS: `srv1775737.hstgr.cloud` (`187.127.32.41`).
- Aplicação: `https://pcpr.gerenciadorviagens.tech`.
- Executor administrativo: `/usr/local/lib/pcpr-main/{receber,politica,atualizar}.sh`.
- Chave exclusiva com `restrict,command=...` no SSH; aceita só `deploy <SHA>`.
- Secret Actions: `PCPR_VPS_SSH_KEY`.
- Variables Actions: `PCPR_VPS_HOST`, `PCPR_VPS_USER`, `PCPR_VPS_KNOWN_HOSTS`.
- Host key fixada; sem descoberta de chave pela rede durante o workflow.

O executor é instalado/atualizado por acesso administrativo, não por scripts
recebidos pelo cliente SSH. Sua chave não permite shell, SFTP, PTY nem forwarding.
O repositório é público, portanto a VPS não recebe credencial GitHub.

## O que ocorre

1. Lock, ambiente PREVIEW, espaço livre mínimo de 5 GiB e SHA atual do main.
2. Sparse checkout e contexto de runtime do commit, sem evidências/imagens de docs.
3. Build rotulado com SHA, sem `.env`/chaves no contexto de build.
4. Checks e plano de migração; ambiente/banco diferentes são recusados.
5. Parada breve de web/worker; dump validado, mídia e hashes consistentes.
6. Migrações pendentes do PREVIEW, sem reset e sem seed.
7. Troca de código/imagem, saúde pública, worker e gravação da versão ativa.

Sem migração, falha após a troca retorna automaticamente ao código anterior.
Após tentativa de migração, falha deixa serviços parados para intervenção: nunca
restaura banco automaticamente nem executa código antigo em esquema alterado.
Outros sites, proxy, Docker daemon e contêiner de banco não são recriados.

## Conferir e operar

- GitHub → Actions → **Publicar main na VPS**: resultado e SHA.
- `/srv/pcpr/app/versao-main.txt`: SHA efetivamente publicado.
- `/srv/pcpr/automatico/implantacoes.tsv`: histórico de sucesso.
- `/srv/pcpr/automatico/logs/`: logs de cada tentativa.
- `/srv/pcpr/automatico/backups/`: banco, mídia e código anterior.
- `curl -fsS https://pcpr.gerenciadorviagens.tech/saude/`: status público.

Backup não é apagado automaticamente. Falta de espaço bloqueia publicação antes
da troca; revisar retenção administrativamente, sem tocar em backups manuais.
Build e troca ainda levam algum tempo; o disparo é automático, não instantâneo.

Para suspender: desabilitar o workflow no GitHub. Para revogar a credencial,
remover apenas a linha de chave com comentário `pcpr-main-actions-20261014` do
authorized_keys e o secret correspondente. Rotação exige nova chave restrita;
não modificar outras chaves. Nunca guardar chave privada no Git.

Validação específica: `bash deploy/automatico/testar-politica.sh`, `bash -n` nos
scripts, ShellCheck e execução real do workflow com comparação do SHA na VPS.
