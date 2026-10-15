# Implantação em VPS (Hostinger) — homologação e produção

Infraestrutura para rodar o PCPR Gestão numa VPS com **Docker Compose**: PostgreSQL,
aplicação (gunicorn + WhiteNoise), worker da outbox, proxy HTTPS, backups externos
criptografados, teste de restauração e monitoramento leve. **Nada aqui altera o código do
produto:** a imagem do produto é construída do commit aprovado com o `Dockerfile` da raiz, sem
alterações, e esta pasta só acrescenta uma camada fina (entrada, health check, rótulos de versão).

> **Estado (2026-10-13).** Tudo foi validado numa **VPS simulada** (Docker em ambiente isolado,
> domínio fictício `homologacao.pcpr.test`, TLS interno). A VPS real ainda **não** foi acessada:
> falta acesso SSH (§1). Ver as evidências em `docs/ops/implantacao-vps-evidencias.md`.
> Produção: `deploy/PRODUCAO.md` (exige autorização explícita).

**Atualização de 14/10/2026:** PREVIEW real em `pcpr.gerenciadorviagens.tech`,
com volumes e Nginx existentes. Atualização manual registrada em
`docs/ops/vps-main-20261014.md`. O deploy imediato a cada push no main dessa
instância é descrito em `deploy/automatico/README.md` (ADR 0037); não ativa produção.

## Sumário
1. [Acesso necessário](#1-acesso-necessário)
2. [Arquitetura](#2-arquitetura)
3. [Primeira instalação](#3-primeira-instalação-homologação)
4. [Implantação e atualização](#4-implantação-e-atualização)
5. [Reversão e recuperação](#5-reversão-e-recuperação)
6. [Backups](#6-backups)
7. [Observabilidade](#7-observabilidade)
8. [Segurança da VPS](#8-segurança-da-vps)
9. [Operação do dia a dia](#9-operação-do-dia-a-dia)
10. [Achados do produto](#10-achados-do-produto-registrados-não-corrigidos-aqui)

---

## 1. Acesso necessário

Para executar na VPS real, uma das opções:

| Opção | O que o dono fornece | Observação |
|---|---|---|
| **A. Executar você mesmo** (recomendada para o primeiro contato) | Roda `deploy/vps/diagnostico.sh` e envia o relatório | Somente leitura; nada é alterado |
| B. Sessão com SSH | IP/porta, usuário com `sudo`, chave SSH dedicada (revogável) | O ambiente de agente na nuvem usado até aqui **bloqueia a porta 22 de saída**; seria preciso um ambiente com SSH liberado |

Também serão necessários: o **domínio autorizado** para homologação (registro DNS `A` — §3.5), um
**e-mail** para o Let's Encrypt, um **destino externo** para backups (§6) e, se o repositório for
privado, uma **deploy key somente leitura** do GitHub para a VPS.

## 2. Arquitetura

```
 Internet ──443/80──► Proxy (Caddy compartilhado OU Nginx existente)       VPS
                        │  TLS, HSTS, 16 MB, bloqueia /media e /var
                        ▼  127.0.0.1:<porta da instância>
             ┌───────── instância "homologacao" (docker compose -p pcpr-homologacao) ─────────┐
             │  web (gunicorn, uid 10001, raiz RO) ──┐                                       │
             │  worker (processar_outbox, LISTEN) ───┼── rede "banco" (internal) ── db (PG 16) │
             │  tarefas: migrar / semear / tarefa ───┘                                       │
             │  ${DADOS}/midia ◄─ PDFs e anexos (só a aplicação)   ${DADOS}/postgres ◄─ banco  │
             └───────────────────────────────────────────────────────────────────────────────┘
 timers systemd: backup diário → dump validado + restic (externo, criptografado)
                 rotinas (cadeia de auditoria) · monitor (5 min) · restauração-teste (mensal)
```

Decisões:
- **Docker Compose**: a imagem de produção já existe no projeto; isola dependências (Pango,
  HarfBuzz) e versões; não conflita com outras aplicações da VPS. Sem Kubernetes.
- **Fila = outbox transacional no PostgreSQL** (`LISTEN/NOTIFY`, `SKIP LOCKED`, retry com
  backoff, `MAX_TENTATIVAS=8` — ADR 0005). **Não** foi introduzido Redis/Celery: a fila real
  do produto já entrega retries seguros e idempotência.
- **Estáticos pelo WhiteNoise** (hash + compressão + cache imutável); o proxy só repassa.
  **Mídia nunca pelo proxy**: o produto não tem rota `/media/`; documentos saem só pelas views
  com autorização por objeto.
- **Proxy**: se a VPS já tiver Nginx/Traefik em 80/443, integrar (`proxy/nginx-site.conf.modelo`);
  senão, um **Caddy compartilhado** (`proxy/compose.yml`, HTTPS automático) atende todas as
  instâncias. Nunca dois proxies na mesma porta.
- **Banco com privilégio mínimo** (`docs/ops/banco.md`): `pcpr_owner` (migrações),
  `pcpr_app` (aplicação: DML; auditoria só INSERT/SELECT), `pcpr_leitura` (SELECT, sem login).
  O superusuário do cluster só administra e faz backup. Porta 5432 **não** é publicada.
- **Homologação = `config.settings.preview` com `DEMO_MODE=false`**: dados 100% sintéticos
  (`semear_demo`, que o produto só permite no PREVIEW) e **login com senha** — a entrada sem
  senha não existe. HTTPS, cookies `Secure` e redirecionamento ligados. O nome do banco termina
  em `_demo` (exigência do check `plataforma.E005`).
- **Produção = `config.settings.production`** (HSTS, `SECURE_SSL_REDIRECT`, segredos obrigatórios).

### Separação dos dados

| O quê | Onde | Permissões |
|---|---|---|
| Código | imagem `pcpr-gestao-implantacao:<commit>-<infra>` | imutável; sem dados/segredos (`.dockerignore`) |
| Configuração/segredos | `/etc/pcpr/<inst>/{app,owner,banco,backup,smoke}.env` | root `0600` (pasta `0700`) |
| Interpolação (não secreta) | `/etc/pcpr/<inst>/instancia.env` | `0644` |
| Banco | `/srv/pcpr/<inst>/dados/postgres` | uid 999 `0700` |
| Documentos e anexos | `/srv/pcpr/<inst>/dados/midia` | uid 10001 `0750` (só web/worker) |
| Temporários | `tmpfs /tmp` em cada contêiner | somem ao reiniciar |
| Logs | `docker compose logs` (json-file, 5×20 MB) + `operacoes.log` + journal | — |
| Backups locais | `/srv/pcpr/<inst>/backups` | root `0750` |
| Backups externos | repositório restic (criptografado) | senha só no `backup.env` **e fora da VPS** |
| Registro de versões | `/srv/pcpr/<inst>/implantacoes.tsv`, `estado/versao-ativa` | — |

## 3. Primeira instalação (homologação)

Pré-requisito: **ler o diagnóstico** e decidir o proxy (§2). Nada abaixo remove ou substitui
serviços existentes.

### 3.1 Diagnóstico (somente leitura)
```bash
sudo bash deploy/vps/diagnostico.sh | tee diagnostico-$(hostname)-$(date +%F).txt
```

### 3.2 Docker (só se ausente — após aprovação)
Repositório oficial da Docker para a distribuição (docs.docker.com/engine/install). Depois,
em `/etc/docker/daemon.json`, rotação de logs padrão
(`{"log-driver":"json-file","log-opts":{"max-size":"20m","max-file":"5"}}`) e `systemctl restart docker`
**somente se não houver contêineres de outras aplicações** (reinicia todos).

### 3.3 Código de infraestrutura
```bash
sudo git clone https://github.com/tiago2904santos/pcpr-gestao-next.git /srv/pcpr/infra
sudo git -C /srv/pcpr/infra checkout <commit-da-branch-de-deploy>   # infraestrutura revisada
```
Repositório privado: deploy key **somente leitura** (`ssh-keygen -t ed25519 -f /root/.ssh/pcpr_deploy`,
cadastrar em *Settings → Deploy keys* sem escrita) e remoto `git@github.com:…`.

### 3.4 Instância
```bash
sudo /srv/pcpr/infra/deploy/vps/preparar-instancia.sh homologacao \
     --dominio homologacao.<domínio-autorizado> --porta 8101
sudoedit /etc/pcpr/homologacao/app.env        # revisar (nunca copiar .env de desenvolvimento)
```
Gera segredos aleatórios (chave Django, senhas dos papéis). Não sobrescreve arquivos existentes.

### 3.5 DNS e proxy (confirmação do dono antes de mudar DNS)
Registro proposto no DNS do domínio autorizado (painel Hostinger → DNS):

| Tipo | Nome | Valor | TTL |
|---|---|---|---|
| A | `homologacao` | `<IP público da VPS — ver diagnóstico>` | 300 (subir para 3600 depois) |
| AAAA | `homologacao` | `<IPv6 da VPS>` (só se o proxy escutar em IPv6) | 300 |

- **Sem proxy na VPS** → Caddy compartilhado:
  ```bash
  sudo install -d -m 0755 /etc/pcpr/proxy/sites
  sed -e 's/DOMINIO/homologacao.<domínio>/g' -e 's/PORTA/8101/g' \
      /srv/pcpr/infra/deploy/proxy/site.caddy.modelo | sudo tee /etc/pcpr/proxy/sites/homologacao.caddy
  echo 'ACME_EMAIL=<e-mail>' | sudo tee /etc/pcpr/proxy/proxy.env
  sudo docker compose -f /srv/pcpr/infra/deploy/proxy/compose.yml --env-file /etc/pcpr/proxy/proxy.env up -d
  ```
  O certificado sai quando o DNS apontar para a VPS e as portas 80/443 estiverem liberadas.
- **Nginx existente** → `proxy/nginx-site.conf.modelo` (trocar `DOMINIO`/`PORTA`), `certbot
  --nginx -d …`, **`nginx -t` antes** do `systemctl reload nginx`.

Até o DNS existir, use `PCPR_SMOKE_MODO=local` no `instancia.env` (smoke pela porta local).

### 3.6 Primeiro deploy (dados sintéticos)
```bash
sudo /srv/pcpr/infra/deploy/vps/implantar.sh homologacao <sha-40-do-produto> --semear
sudo /srv/pcpr/infra/deploy/vps/pcpr.sh homologacao senha demo          # senha forte
sudo /srv/pcpr/infra/deploy/vps/pcpr.sh homologacao senha consulta.demo # perfil de consulta
printf 'PCPR_SMOKE_USUARIO=demo\nPCPR_SMOKE_SENHA=…\n' | sudo tee /etc/pcpr/homologacao/smoke.env
sudo chmod 600 /etc/pcpr/homologacao/smoke.env
```
Os usuários do dataset nascem **sem senha utilizável**; sem `DEMO_MODE` ninguém entra até a
senha ser definida. (A mensagem final de `semear_demo` sobre "campos vazios" vale só no PREVIEW.)

### 3.7 Testes de homologação (pelo endereço implantado)
```bash
sudo deploy/vps/smoke.sh homologacao                       # saúde, cabeçalhos, TLS, login, PDF
sudo deploy/homologacao/testar-documentos.sh homologacao   # worker, versões, retry, download
sudo deploy/homologacao/testar-classes.sh homologacao      # todas as classes documentais
sudo deploy/homologacao/comparar-renderizacao.sh homologacao   # VPS reproduz o PDF gravado
# de uma estação com o repositório (navegador real, 360 e 1440 px):
HOMOLOGACAO_URL=https://homologacao.<domínio> HOMOLOGACAO_USUARIO=demo HOMOLOGACAO_SENHA=… \
HOMOLOGACAO_CONSULTA_USUARIO=consulta.demo HOMOLOGACAO_CONSULTA_SENHA=… \
  uv run python deploy/homologacao/roteiro_navegador.py
```

### 3.8 Backups e timers
```bash
sudoedit /etc/pcpr/homologacao/backup.env      # §6
sudo deploy/vps/backup.sh homologacao --iniciar-repositorio
sudo deploy/vps/backup.sh homologacao --motivo manual
sudo deploy/vps/restaurar-teste.sh homologacao --origem externo   # prova a recuperação
sudo deploy/vps/instalar-timers.sh homologacao
```

## 4. Implantação e atualização

`deploy/vps/implantar.sh <instância> <sha-40>` — **nunca** nome de branch:

1. valida o commit (existe; com **dados reais** — `app.env` fora de `config.settings.preview`/
   `APP_ENV=preview`, qualquer que seja o nome da instância —, consta de
   `/etc/pcpr/<instância>/aprovados.txt`, e `--sem-backup`/`--semear` são recusados);
2. constrói `pcpr-gestao:<sha>` com `git archive <sha> | docker build -` (exatamente o commit,
   sem arquivos locais) e a camada `pcpr-gestao-implantacao:<sha12>-<infra12>`. O `Dockerfile`
   do produto parte de uma tag móvel (`python:3.13-slim`); por isso, com dados reais, a imagem
   do produto **tem de ser a já construída e testada na homologação deste host** — o script
   recusa reconstruí-la sem `--construir-base` (decisão explícita: camadas não testadas). O ID
   da imagem fica registrado em `implantacoes.tsv`;
3. `check --deploy` da nova imagem (falha em ERROR) antes de tocar no que está no ar;
4. backup prévio (dump validado + cópia externa);
5. migrações com o papel dono (`migrar`) + privilégios pós-migração. Se há migração
   pendente, **web e worker param antes** (o código antigo não roda contra um schema novo nem
   parcial); se a migração falhar, ficam parados e o alerta é crítico (§5);
6. troca a versão em `instancia.env` (guarda a anterior);
7. `docker compose up -d --wait` (web e worker; banco intacto);
8. saúde (health check do contêiner);
9. smoke test pelo endereço público;
10. registra em `implantacoes.tsv` e `estado/versao-ativa`; limpa imagens antigas preservando
    atual e anterior de todas as instâncias.

Falha **sem migração nova** → volta sozinho para a imagem anterior. Falha **com migração** →
para e alerta: a reversão exige decisão humana (§5). A troca de web/worker causa alguns
segundos de indisponibilidade (instância única), e a migração, a duração dela — em produção,
dentro da janela.

Atualizar a infraestrutura: `git -C /srv/pcpr/infra pull` (ou checkout do commit revisado) e
reimplantar o mesmo commit do produto — o script recusa `deploy/` com mudanças não commitadas.

## 5. Reversão e recuperação

| Situação | Ação |
|---|---|
| Nova versão com defeito, **sem** migração | `pcpr.sh <inst> reverter` (troca a imagem; banco intacto; smoke) |
| Nova versão com defeito, **com** migração | decidir: corrigir para frente **ou** `pcpr.sh <inst> reverter <dump-pre-implantacao> --confirmo-sobrescrever-<inst>` — uma operação só: para web/worker, backup, restaura o banco e **só então** sobe a imagem anterior (perde o que foi gravado depois do dump). Sem o dump, `reverter` recusa |
| Migração falhou no meio da implantação (o alerta diz quantas foram gravadas) | a imagem ativa ainda é a anterior, mas o schema andou: `reiniciar` e `reverter` recusam. Recuperar com `pcpr.sh <inst> restaurar-banco <dump-pre-implantacao> --confirmo-sobrescrever-<inst>` (o caminho aparece em `pcpr.sh <inst> reiniciar`) ou reimplantar a versão corrigida |
| Exclusão acidental / corrupção lógica | `restaurar-teste.sh` para examinar; `pcpr.sh <inst> restaurar-banco <dump> --confirmo-sobrescrever-<inst>` (confere o dump com `pg_restore --list` e o `.sha256` **antes** de apagar; para web/worker e faz backup antes; depois confere se todo anexo referenciado existe em `dados/midia` — faltando algum, web/worker ficam parados e o alerta diz como recuperá-lo do restic) |
| Documento apagado/corrompido no disco | `restic restore` do caminho (`/dados/midia/...`); conferir com o SHA-256 em `viagens_documento` |
| Falha de disco / perda total da VPS | nova VPS → §3.2–3.4 → `restic restore latest --target /restauro` → copiar `dados/midia`, criar o cluster (`implantar.sh` com o mesmo commit — na VPS nova a imagem do produto não existe: homologar de novo ou, por decisão registrada, `--construir-base`) e `restaurar-banco` com o dump restaurado |

## 6. Backups

- **Diário (02:20)**: `pg_dump -Fc` pelo superusuário (snapshot consistente), papéis globais
  (sem senhas), validação com `pg_restore --list` + SHA-256; retenção local de 7 dias.
- **Externo**: `restic` (imagem fixada por digest) envia dumps **e** documentos —
  criptografia AES-256 no cliente, deduplicação, retenção 14 diários / 8 semanais / 12 mensais,
  `restic check` diário (5% dos dados aos domingos). Banco e documentos são do mesmo instante:
  web e worker ficam congelados (`docker compose pause`, as requisições esperam) só durante o
  dump e uma cópia por hardlinks da pasta de documentos; o envio parte dessa cópia.
- **Destino externo** (decisão do dono — nada foi contratado): um backend do restic
  configurável só por variáveis de ambiente — `rest:` (rest-server em outro servidor, HTTPS
  com usuário e senha), `s3:` (bucket S3-compatível) ou `b2:`. `sftp:` e `rclone:` exigem chave
  SSH ou arquivo de configuração dentro do contêiner e **não** são suportados pelo `backup.sh`. **Guarde a senha do repositório fora da VPS** (cofre de senhas): sem ela não
  há restauração.
- **Backup nativo da Hostinger** (snapshot/backup semanal da VPS no painel): complementar e
  útil contra perda total, mas não é consistente com o banco nem fica fora do provedor — não
  substitui o restic.
- **Teste de restauração mensal** (1º domingo): baixa o snapshot externo, sobe um PostgreSQL
  **isolado** (rede interna própria, `tmpfs`), restaura, roda `verificar_auditoria` do produto
  e confere o SHA-256 de todos os PDFs. Falha = alerta.
- RPO: 24 h (dump diário) — para menos, ativar arquivamento de WAL (PITR) em produção.
  RTO estimado: < 1 h com a imagem já construída.

## 7. Observabilidade

Sem stack pesada: `monitorar.sh` a cada 5 min (custo desprezível) verifica contêineres e
saúde, aumento de reinícios, `/saude/` pelo endereço público, validade do certificado
(< 14 dias), disco (/ e dados ≥ 85%), memória, carga, mensagens da outbox com falha ou paradas
há > 15 min (worker travado), documentos com falha de geração, idade do último backup e do
último backup externo (> 26 h), do último teste de restauração (> 35 dias) e da verificação
da cadeia de auditoria (> 26 h). Alerta apenas quando o conjunto de problemas muda.

Alertas: journal (`journalctl -t pcpr-<inst>`), `/srv/pcpr/<inst>/operacoes.log` e, se
configurado, webhook em `/etc/pcpr/alertas.env` (`PCPR_ALERTA_URL`, `PCPR_ALERTA_FORMATO=
texto|slack|discord` — ex.: tópico privado do ntfy ou canal institucional).

**Segredos fora dos logs:** o token do feed ICS da agenda (`/agenda/ics/<token>.ics`) é a
única credencial do feed. A aplicação já o mascara nos próprios logs; o log de acesso do
Gunicorn (`docker/gunicorn_conf.py`), o do Caddy (`format filter` em `proxy/site.caddy.modelo`)
e o do Nginx (`log_format pcpr_PORTA`) gravam `/agenda/ics/[token]`. O `error_log` do Nginx
pode citar a linha da requisição: mantenha-o legível só por root/adm.

## 8. Segurança da VPS

Já garantido pela stack: banco sem porta publicada, aplicação só em `127.0.0.1`, contêineres
com `no-new-privileges`, `cap_drop: ALL`, raiz somente leitura, uid dedicado; segredos fora do
Git (`0600`); mídia fora do proxy; `DEMO_MODE` proibido fora do PREVIEW (o produto recusa).

Propostas (aplicar **depois** do diagnóstico, uma por vez, com reversão pronta):

| Controle | Como aplicar sem perder o acesso |
|---|---|
| SSH só por chave | 1) instalar a chave e **testar o login numa 2ª sessão**; 2) `PasswordAuthentication no`, `PermitRootLogin prohibit-password` em `/etc/ssh/sshd_config.d/60-pcpr.conf`; 3) `sshd -t`; 4) `systemctl reload ssh` **mantendo a sessão atual aberta**; 5) testar de novo em outra sessão. Reversão: apagar o arquivo e recarregar. O console VNC/navegador do painel Hostinger é a saída de emergência. |
| Firewall | Preferir o **firewall do painel Hostinger** (fora da VPS, não derruba a sessão). No host: `ufw allow OpenSSH` **antes** de `ufw enable`; liberar só 80/443. Atenção: portas publicadas pelo Docker em `0.0.0.0` **ignoram** o UFW — por isso a stack publica apenas em `127.0.0.1`. |
| Tentativas de acesso | `fail2ban` (jail `sshd`) ou CrowdSec; não bloquear o IP administrativo. |
| Atualizações | `unattended-upgrades` só com origem `-security`; reinício planejado quando `/var/run/reboot-required`. Imagens: reimplantar após atualização do `python:3.13-slim`/PostgreSQL (digest novo, revisado). |
| Acesso administrativo | usuário próprio com `sudo`; root sem senha; chave dedicada para automação, revogável. |
| Painéis | nada administrativo exposto: sem Django admin, sem Adminer/pgAdmin, sem métricas públicas. |

## 9. Operação do dia a dia

```bash
deploy/vps/pcpr.sh homologacao status          # serviços, versão, verificações
deploy/vps/pcpr.sh homologacao logs web        # (worker | db)
deploy/vps/pcpr.sh homologacao reiniciar
deploy/vps/pcpr.sh homologacao senha <login>
deploy/vps/pcpr.sh homologacao manage <comando> # ex.: verificar_auditoria
systemctl list-timers 'pcpr-*'
```

Capacidade medida (repouso, dataset de 258 ofícios): web ~300 MiB (3 workers), worker ~70 MiB,
PostgreSQL ~80 MiB, Caddy ~13 MiB; banco 129 MB e documentos 48 MB. Construir a imagem exige
espaço para ~2,5 GB de camadas (estimativa: ≥ 2 GB de RAM livre durante o build). Para homologação + produção na mesma VPS: **≥ 2 vCPU e
8 GB RAM** (KVM 2 ou superior); com 4 GB, rodar uma instância por vez e `WEB_CONCURRENCY=2`.

## 10. Achados do produto (registrados, não corrigidos aqui)

1. **`check --deploy` falha com `mail.E001`** (Django 6.1) quando não há SMTP — inclusive no
   `scripts/preview-entrypoint.sh` do commit `b3471bd`, que por isso **não sobe** o contêiner do
   PREVIEW. **Corrigido em STAGING/PRODUCTION** (`config/settings/production_base.py`: silencia
   `mail.E001` só sem SMTP e com `NOTIFICACOES_POR_EMAIL=false`). O PREVIEW (homologação com
   dados sintéticos) segue coberto pela mesma regra em `deploy/docker/verificar.py`.
2. **Bloqueio de login por IP usa `REMOTE_ADDR`** (`gestao/identidade/forms.py`); atrás de
   proxy é o IP do proxy, então o bloqueio vale por e-mail (mais restritivo, não inseguro).
   A auditoria usa `X-Real-IP`, que os proxies daqui sobrescrevem.
3. Ambiente de desenvolvimento sem `libharfbuzz-subset`: os PDFs locais são equivalentes
   (páginas, fontes, texto), mas não idênticos em bytes aos da imagem.
4. `semear_demo` termina dizendo "deixe os campos vazios" mesmo com `DEMO_MODE=false`.
