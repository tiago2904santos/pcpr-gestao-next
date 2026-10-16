# Publicação automática do main na VPS

Solicitação de 14/10/2026: toda atualização enviada ao `main` deve iniciar a
implantação imediatamente, sem confirmação manual e sem aguardar a suíte longa.
Alterações locais e branches diferentes não disparam a publicação.

Escopo: PREVIEW existente em `pcpr.gerenciadorviagens.tech`, com dados fictícios.
Não ativar produção, não resetar nem semear dados, não alterar outros serviços.
Cada implantação usa o SHA imutável recebido do GitHub, confirmado como ponta do
main. Execuções obsoletas são descartadas; duas implantações nunca se sobrepõem.

Antes da troca: construir a imagem, conferir ambiente/banco esperado e checks,
guardar código anterior e backup consistente de banco e mídia. Migrações do
PREVIEW são aplicadas com web/worker parados. Sem migração, falha de saúde restaura
o código anterior; após tentativa de migração, falha exige intervenção, sem
restaurar dados ou executar código antigo contra esquema possivelmente alterado.

Credencial exclusiva no GitHub Secrets, comando SSH restrito e host key fixada.
Nenhuma chave privada ou `.env` entra no Git. Logs/versionamento permitem conferir
qual SHA está no ar. Falha bloqueia a troca e aparece na execução do GitHub Actions.
Backups não são apagados automaticamente; espaço insuficiente impede nova troca.

Autorização de 16/10/2026: ativar também o importador no PREVIEW hospedado.
Web, worker e importador usam a mesma imagem e param antes de backup/migrações.
O banco existente entra adicionalmente na rede interna de processamento, com alias
`db`, sem recriar seu contêiner nem publicar portas. A reversão respeita os serviços
presentes na versão anterior. O proxy desta aplicação aceita 32 MB; demais sites
e regras de autenticação permanecem intactos. Validar envio e processamento no HTTPS.
