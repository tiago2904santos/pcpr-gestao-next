# Ativação em PRODUÇÃO — plano (NÃO executado)

Produção só depois da homologação aprovada **e** de autorização explícita do dono do produto e
das aprovações institucionais aplicáveis. HTTPS funcionando **não** é, por si só, liberação para
dados institucionais reais.

## 1. Pré-requisitos (checklist de autorização)
- [ ] Homologação aprovada no endereço definitivo, com o mesmo commit candidato (§2), incluindo
      `smoke.sh`, `testar-documentos.sh`, `testar-classes.sh` e `roteiro_navegador.py` verdes.
- [ ] Autorização registrada (quem, quando, qual commit) — e o commit em
      `/etc/pcpr/producao/aprovados.txt` (o `implantar.sh` recusa commit não aprovado).
- [ ] Domínio de produção definido e DNS autorizado; certificado válido.
- [ ] Backup externo de produção configurado **em repositório separado** do de homologação,
      senha guardada fora da VPS, e uma restauração-teste aprovada **antes** de dados reais.
- [ ] Alertas chegando a um canal monitorado (`/etc/pcpr/alertas.env`).
- [ ] Controles de segurança da VPS aplicados (`deploy/README.md` §8) — SSH por chave e firewall.
- [ ] SMTP institucional autorizado (se as notificações por e-mail forem ligadas).
- [ ] Integrações (eProtocolo) com credenciais oficiais; até lá, `EPROTOCOLO_AMBIENTE=simulado`
      e `EPROTOCOLO_SOMENTE_LEITURA=true`.
- [ ] Decisão sobre PITR (arquivamento de WAL) se RPO de 24 h for insuficiente.
- [ ] Plano de carga inicial de dados aprovado (§3).

## 2. Versão aprovada
- Um **commit imutável** (SHA de 40 caracteres) — de preferência com tag anotada
  (`v1.0.0`) — que passou na homologação. Nunca o "último da branch".
- Registrado em `implantacoes.tsv` (produto, infraestrutura, imagem, operador).

## 3. Migração de dados
- O banco do sistema anterior **não** será copiado sem autorização e plano próprio
  (mapeamento, anonimização para ensaio, validação, responsável).
- Se não houver migração: produção começa vazia; cadastros institucionais (unidades,
  servidores, tabelas de diária, configuração) são feitos pelos administradores — e o
  primeiro administrador é criado com `pcpr.sh producao compose run --rm tarefa createsuperuser` (interativo) **na janela**.
- Se houver: ensaio completo na homologação com cópia **anonimizada**, comparação de
  contagens/totais, e só então a carga real dentro da janela.

## 4. Preparação (antes da janela)
```bash
sudo deploy/vps/preparar-instancia.sh producao --dominio <domínio-produção> --porta 8102 \
     --settings config.settings.production
sudoedit /etc/pcpr/producao/app.env      # revisar: DEMO_MODE=false, SMTP, ROTAS, integrações
echo <sha-aprovado> | sudo tee -a /etc/pcpr/producao/aprovados.txt
sudoedit /etc/pcpr/producao/backup.env   # repositório EXTERNO próprio da produção
```
Proxy: novo site (`proxy/site.caddy.modelo` ou `proxy/nginx-site.conf.modelo`) apontando para
a porta 8102. Ajustar recursos no `instancia.env` (memória, `WEB_CONCURRENCY`).

## 5. Janela de implantação (sugestão: fora do expediente, 1 h, com responsável de plantão)
1. Comunicar o início; congelar mudanças.
2. `implantar.sh producao <sha-aprovado>` (constrói, verifica, migra, sobe, smoke).
3. Criar o primeiro administrador; `smoke.env` de produção com um usuário de teste **sem dados
   reais sensíveis** (ou só o smoke anônimo).
4. `backup.sh producao --iniciar-repositorio` e `backup.sh producao --motivo manual`;
   `restaurar-teste.sh producao --origem externo` (isolado, não toca na produção).
5. `instalar-timers.sh producao`.
6. Validação pós-deploy (§6). Comunicar o fim.

## 6. Validação pós-deploy
- `smoke.sh producao` verde (HTTPS, HSTS, cookies `Secure`, sem DEMO, PDF protegido).
- Login real de um administrador; criação de um ofício de teste **marcado como teste** e
  cancelado em seguida (o produto não apaga — fica no histórico/auditoria).
- `pcpr.sh producao manage verificar_auditoria` íntegro.
- `monitorar.sh producao --mostrar` sem problemas.
- **Nunca** rodar `testar-documentos.sh`, `testar-classes.sh` nem `semear` em produção (os scripts
  recusam).

## 7. Rollback
- Até a primeira gravação real: `pcpr.sh producao reverter` (imagem anterior) ou desligar o
  site no proxy.
- Com migração aplicada e defeito grave: `reverter` + `restaurar-banco` com o dump
  `*-pre-implantacao.dump` gerado na própria janela (perde o que foi gravado depois — decisão
  do responsável).
- Retirar do ar sem perder nada: `pcpr.sh producao compose stop web worker` (banco e arquivos
  intactos) e página de manutenção no proxy.

## 8. Monitoramento inicial (primeiras 2 semanas)
- Revisar diariamente `operacoes.log`, `journalctl -t pcpr-producao`, outbox com falhas,
  uso de disco e o resultado do backup externo.
- Primeiro teste de restauração mensal acompanhado.
- Ajustar `WEB_CONCURRENCY`, memória e `shared_buffers` com base no uso real.

## 9. Recuperação
Ver `deploy/README.md` §5 (exclusão acidental, corrupção, falha de atualização, falha de disco,
perda total da VPS). O procedimento de perda total deve ser **ensaiado** numa VPS temporária
antes de dados reais.
