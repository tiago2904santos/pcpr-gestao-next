# VPS Hostinger com o template "Docker + n8n" — sistema novo como produção única

A VPS foi reinstalada pelo template da Hostinger (Ubuntu + Docker + n8n). O template sobe um
**Traefik** (portas 80/443, certificados Let's Encrypt) e o **n8n**, num projeto Compose próprio.
Aqui o PCPR entra **ao lado** desse projeto, sem alterar o arquivo do template:

```
Internet ──443──▶ Traefik (template)
                    ├─ n8n.<domínio>          → n8n (editor com login, HTTPS)
                    ├─ <domínio>              → pcpr-web:8000 (menos /api/automacao, /media, /var)
                    └─ eventos./pcpr./www.    → 301 para <domínio>
rede do Traefik (externa):  n8n ⇄ pcpr-web:8000/api/automacao (token)   pcpr-automacao → n8n:5678/webhook (HMAC)
rede "banco" (interna):     db ⇄ web, worker, importador, automacao, ia      (sem porta publicada)
```

Arquivos: `deploy/compose.yml` (base, igual às outras instâncias) + `compose.hostinger.yml`
(sobreposição: sem porta no host, rótulos do Traefik, rede compartilhada com o n8n). O
`deploy/vps/lib.sh` inclui a sobreposição quando o `instancia.env` define
`PCPR_COMPOSE_EXTRA=hostinger/compose.hostinger.yml`.

## 0. Inspeção (antes de qualquer mudança)

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'
docker network ls
ls /docker/n8n && cat /docker/n8n/docker-compose.yml   # template (só leitura)
sed 's/=.*/=…/' /docker/n8n/.env                        # nomes das variáveis, sem valores
df -h / && free -h && swapon --show
```

Anotar: rede do Traefik (`TRAEFIK_REDE`, ex.: `n8n_default`), nome do *certresolver*
(`TRAEFIK_CERTRESOLVER`, ex.: `mytlschallenge`), entrada TLS (`websecure`), se o n8n usa SQLite
ou PostgreSQL e o nome do serviço do n8n na rede (`n8n`). **Backup antes de mexer**: `docker
compose -f /docker/n8n/docker-compose.yml stop n8n`, cópia do volume de dados do n8n e da chave
`N8N_ENCRYPTION_KEY` para fora da VPS, `start` de novo.

## 1. DNS (painel do domínio)

| Registro | Valor |
|---|---|
| `A @` | IP da VPS |
| `A n8n` / `A eventos` / `A pcpr` / `A www` | IP da VPS |

O Traefik só emite o certificado depois que o DNS aponta para a VPS.

## 2. Preparar a instância

```bash
git clone https://github.com/tiago2904santos/pcpr-gestao-next /srv/pcpr/infra
cd /srv/pcpr/infra
sudo deploy/vps/preparar-instancia.sh producao --dominio gerenciadorviagens.tech --porta 8102 \
     --settings config.settings.production
sudoedit /etc/pcpr/producao/instancia.env
#   PCPR_COMPOSE_EXTRA=hostinger/compose.hostinger.yml
#   PCPR_DOMINIO=gerenciadorviagens.tech
#   TRAEFIK_REDE=<anotado no passo 0>
#   TRAEFIK_CERTRESOLVER=<anotado no passo 0>
sudoedit /etc/pcpr/producao/app.env
#   DJANGO_ALLOWED_HOSTS=gerenciadorviagens.tech,pcpr-web
#   DJANGO_CSRF_TRUSTED_ORIGINS=https://gerenciadorviagens.tech
#   DEMO_MODE=false   APP_ENV=production
#   AUTOMACAO_TRANSPORTE=manual          (envios manuais pelo WhatsApp do operador)
#   WHATSAPP_MODO=simulado  IA_MODO=simulado   (canais reais só com credenciais oficiais)
#   IA_HABILITADA=false  AUTOMACAO_HABILITADA=false  EPROTOCOLO_HABILITADO=false   (ADR 0050)
echo <sha-aprovado> | sudo tee -a /etc/pcpr/producao/aprovados.txt
```

`pcpr-web` em `DJANGO_ALLOWED_HOSTS` é o nome pelo qual o n8n chama a API na rede interna; o
Traefik nunca encaminha esse `Host` (não há rota pública para ele).

## 3. Implantar a versão

```bash
sudo deploy/vps/implantar.sh producao <sha-aprovado> --construir-base
```

Banco novo vazio → as migrações criam o schema. Não rodar `semear` (o script recusa).

## 4. Carga dos dados migrados (GV + EV)

A migração roda **fora da VPS**, sobre a cópia restaurada dos dois sistemas
(`manage.py importar_legado --gravar`, relatório de conferência em JSON). O resultado é um dump
do banco novo já com os dados:

```bash
# máquina local
pg_dump -Fc -d pcpr_destino -f pcpr-carga.dump && sha256sum pcpr-carga.dump > pcpr-carga.dump.sha256
scp pcpr-carga.dump* root@<vps>:/srv/pcpr/producao/backups/banco/
rsync -a --info=progress2 <midia-migrada>/ root@<vps>:/srv/pcpr/producao/dados/midia/
# VPS (janela; web e workers parados)
sudo deploy/vps/pcpr.sh producao restaurar-banco /srv/pcpr/producao/backups/banco/pcpr-carga.dump \
     --confirmo-sobrescrever-producao
sudo chown -R 10001:10001 /srv/pcpr/producao/dados/midia
```

O dump e a mídia são dados pessoais: transferir só por SSH, nunca por URL aberta; apagar as
cópias temporárias depois da conferência.

## 5. Conferência

```bash
sudo deploy/vps/smoke.sh producao
sudo deploy/vps/pcpr.sh producao manage verificar_auditoria
sudo deploy/vps/pcpr.sh producao compose exec db psql -U postgres -d "$PCPR_DB_NOME" -c \
  "select (select count(*) from cadastros_servidor) servidores, (select count(*) from identidade_usuario) usuarios"
# os números têm de bater com o relatório da migração (mesmo dump, conferido pelo SHA-256)
curl -sI https://eventos.gerenciadorviagens.tech/ | grep -i location   # 301 → principal
curl -s -o /dev/null -w '%{http_code}\n' https://gerenciadorviagens.tech/api/automacao/v1/estado  # 404
```

Login de um administrador migrado com a senha antiga.

## Recursos desligados (ADR 0050)

A versão em uso roda **sem IA, sem automações e sem eProtocolo**: `IA_HABILITADA=false`,
`AUTOMACAO_HABILITADA=false` e `EPROTOCOLO_HABILITADO=false` no `app.env` (é também o padrão de
`config.settings.production` quando a variável falta). Efeito: Automação, Assistência e Central
de ajuda somem do menu e respondem 404, assim como `/api/automacao/` e o webhook do WhatsApp; os
workers `automacao` e `ia` ficam parados (podem ser desligados: `pcpr.sh producao compose stop
automacao ia`); nenhum evento vai ao n8n, então `N8N_EVENTOS_URL`/`N8N_EVENTOS_SEGREDO` podem
ficar vazios. Continuam: Pendências, envios manuais (PDFs, `wa.me`, confirmação à mão, link de
KM) e o número do protocolo digitado à mão. Religar = trocar a variável para `true` e
`pcpr.sh producao reiniciar`; nada foi apagado.

## 6. Integração com o n8n (só com `AUTOMACAO_HABILITADA=true`)

1. No PCPR (Automação → Credenciais): emitir o token de **transporte** do n8n.
2. No n8n (`https://n8n.gerenciadorviagens.tech`): criar as credenciais com os nomes de
   `docs/automacao/n8n/pcpr/README.md` (token da API, segredo HMAC), importar
   `docs/automacao/n8n/pcpr/w*.json` (chegam **desativados**) e trocar a URL-base da API por
   `http://pcpr-web:8000/api/automacao/v1`.
3. `app.env`: `N8N_EVENTOS_URL=http://n8n:5678/webhook/pcpr-eventos`, `N8N_EVENTOS_SEGREDO=<o
   mesmo HMAC>`, `AUTOMACAO_TRANSPORTE=n8n`; `pcpr.sh producao reiniciar`.
4. Ativar os workflows um a um e conferir em Automação → Painel (eventos entregues, nenhuma
   exceção).

O n8n não recebe credencial do banco nem cookies de usuário: só o token da API (escopos de
transporte) e o segredo HMAC.

## 7. Backups e timers

```bash
sudoedit /etc/pcpr/producao/backup.env    # repositório EXTERNO (restic), senha fora da VPS
sudo deploy/vps/backup.sh producao --iniciar-repositorio
sudo deploy/vps/backup.sh producao --motivo manual
sudo deploy/vps/restaurar-teste.sh producao --origem externo
sudo deploy/vps/instalar-timers.sh producao
```

## Reverter

- Antes da carga: `docker compose -p pcpr-producao … down` — o template (Traefik + n8n) não é
  tocado em nenhum passo.
- Depois da carga: `pcpr.sh producao reverter <*-pre-implantacao.dump>
  --confirmo-sobrescrever-producao`.

## Estado desta VPS (19/10/2026)

Implantado o commit `a9e998e` (ramo `release/producao-2026-10-19`: PR #25 + PR #24 até a 12ª
revisão + migração dos sistemas antigos + este pacote). Valores encontrados no template:

| Item | Valor |
|---|---|
| Traefik | `/docker/traefik`, `network_mode: host`, resolver `letsencrypt` (desafio HTTP), entrada `websecure`, HTTP → HTTPS global |
| n8n | `/docker/n8n-mrbk` (projeto `n8n-mrbk`), SQLite no volume `n8n-mrbk_n8n_data`, versão 2.43.7 |
| `TRAEFIK_REDE` | `n8n-mrbk_default` (o serviço do n8n atende por `n8n` nessa rede) |

Mudanças feitas no template (cópia do original em `/docker/n8n-mrbk/docker-compose.yml.original-hostinger`
e backup completo em `/root/backup-antes-pcpr-*`): sem porta publicada (antes `0.0.0.0:32768`, HTTP
sem TLS); `N8N_SECURE_COOKIE=true`; rota extra `n8n.gerenciadorviagens.tech` (precisa do registro
DNS `A n8n`); `N8N_SSRF_ALLOWED_HOSTNAMES=pcpr-web,graph.facebook.com`; poda de execuções. Se o
painel da Hostinger reimplantar o n8n, essas mudanças precisam ser refeitas.

Host: swap de 4 GB; `ufw` liberando só 22, 80 e 443.

**Carga dos dados migrados** (feita uma vez, `/root/carregar-dados.sh`): web e worker parados,
mídia copiada para `dados/midia` (dono 10001), banco recriado com dono `pcpr_owner` e
`pg_restore --no-owner --no-privileges --role=pcpr_owner` (o dump veio de um banco local sem os
papéis), depois `migrar` (aplica os privilégios de `pcpr_app`) e subida. Conferido: contagens
iguais às do ensaio local, 0 anexo ausente, cadeia de auditoria íntegra.

**n8n** (`/root/integrar-n8n.sh`): credencial de transporte (180 dias) emitida por um
administrador, segredos em `/etc/pcpr/producao/n8n.env` (0600); credenciais `pcprApiToken0001`,
`pcprHmacEventos1`, `pcprWebhookInt01` e os 7 fluxos importados **desativados**, apontando para
`http://pcpr-web:8000/api/automacao/v1`. `AUTOMACAO_TRANSPORTE=manual` até haver a conta oficial
do WhatsApp; ligar = `AUTOMACAO_TRANSPORTE=n8n` no `app.env`, recriar web/worker/automacao e
publicar os fluxos na ordem do README dos fluxos.

Pendências: backup externo (`/etc/pcpr/producao/backup.env`, repositório restic fora da VPS);
renovar a credencial de transporte antes de 180 dias.
