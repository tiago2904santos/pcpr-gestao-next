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
#   AUTOMACAO_TRANSPORTE=manual          (n8n liga depois do passo 6)
#   WHATSAPP_MODO=simulado  IA_MODO=simulado   (canais reais só com credenciais oficiais)
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

## 6. Integração com o n8n

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
