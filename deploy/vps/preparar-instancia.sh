#!/usr/bin/env bash
# Prepara pastas, configuração e segredos de uma instância. NÃO sobrescreve nada existente.
#
#   sudo deploy/vps/preparar-instancia.sh homologacao --dominio homologacao.exemplo.gov.br \
#        --porta 8101 [--settings config.settings.preview]
#   sudo deploy/vps/preparar-instancia.sh producao --dominio gestao.exemplo.gov.br --porta 8102 \
#        --settings config.settings.production
#
# HOMOLOGAÇÃO usa config.settings.preview com DEMO_MODE=false: dados 100% sintéticos
# (semear_demo) e login com senha. PRODUÇÃO usa config.settings.production (dados reais).
. "$(dirname "$0")/lib.sh"

INST="${1:-}"; shift || true
DOMINIO=""; PORTA=""; SETTINGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dominio) DOMINIO="$2"; shift 2 ;;
    --porta) PORTA="$2"; shift 2 ;;
    --settings) SETTINGS="$2"; shift 2 ;;
    *) morrer "opção desconhecida: $1" ;;
  esac
done
[[ "$INST" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || morrer "uso: $0 <instância> --dominio <fqdn> --porta <n>"
[[ "$DOMINIO" =~ ^[a-z0-9.-]+\.[a-z]{2,}$ ]] || morrer "--dominio inválido"
[[ "$PORTA" =~ ^[0-9]{4,5}$ ]] && [ "$PORTA" -ge 1024 ] && [ "$PORTA" -le 65535 ] \
  || morrer "--porta inválida (1024–65535)"
[ "$(id -u)" = 0 ] || morrer "rode como root (cria /etc/pcpr e ajusta donos)"

if [ -z "$SETTINGS" ]; then
  case "$INST" in
    producao) SETTINGS=config.settings.production ;;
    *) SETTINGS=config.settings.preview ;;
  esac
fi
case "$SETTINGS" in
  config.settings.preview) APP_ENV=preview; DB="pcpr_${INST//-/_}_demo" ;;
  config.settings.staging) APP_ENV=staging; DB="pcpr_${INST//-/_}" ;;
  config.settings.production) APP_ENV=production; DB="pcpr_${INST//-/_}" ;;
  *) morrer "settings não suportado: $SETTINGS" ;;
esac

if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${PORTA}\$"; then
  morrer "a porta $PORTA já está em uso no host"
fi
# Também as reservadas por instâncias paradas ou ainda não implantadas.
for outra in "$PCPR_ETC"/*/instancia.env; do
  [ -f "$outra" ] && [ "$outra" != "$PCPR_ETC/$INST/instancia.env" ] || continue
  ! grep -qx "PCPR_PORTA=$PORTA" "$outra" || morrer "a porta $PORTA já é da instância $(basename "$(dirname "$outra")")"
done

CONF="$PCPR_ETC/$INST"
install -d -m 0711 "$PCPR_ETC"
install -d -m 0700 "$CONF"
install -d -m 0750 "$PCPR_RAIZ" "$PCPR_RAIZ/$INST" "$PCPR_RAIZ/$INST/dados" \
  "$PCPR_RAIZ/$INST/backups" "$PCPR_RAIZ/$INST/backups/banco" "$PCPR_RAIZ/$INST/estado"
# Banco: uid/gid 999 = usuário postgres da imagem oficial (Debian).
install -d -m 0700 -o 999 -g 999 "$PCPR_RAIZ/$INST/dados/postgres"
# Documentos: só o usuário da aplicação nos contêineres (uid dedicado 10001) lê e escreve.
install -d -m 0750 -o 10001 -g 10001 "$PCPR_RAIZ/$INST/dados/midia"

segredo() { python3 -c 'import secrets; print(secrets.token_urlsafe(40))'; }
criar() {  # criar <arquivo> <modo> — só cria se não existir; conteúdo pela entrada padrão
  local arq="$1" modo="$2"
  if [ -e "$arq" ]; then echo "mantido (já existe): $arq"; cat >/dev/null; return; fi
  ( umask 077; cat >"$arq" ); chmod "$modo" "$arq"; echo "criado: $arq"
}

OWNER_SENHA="$(segredo)"; APP_SENHA="$(segredo)"
if [ -f "$CONF/banco.env" ]; then
  OWNER_SENHA="$(sed -n 's/^PCPR_OWNER_PASSWORD=//p' "$CONF/banco.env")"
  APP_SENHA="$(sed -n 's/^PCPR_APP_PASSWORD=//p' "$CONF/banco.env")"
fi

criar "$CONF/instancia.env" 0644 <<EOF
# Interpolação do deploy/compose.yml (não secreto). Gerado em $(date -I).
PCPR_INSTANCIA=$INST
PCPR_CONFIG=$CONF
PCPR_DADOS=$PCPR_RAIZ/$INST/dados
PCPR_PORTA=$PORTA
PCPR_DOMINIO=$DOMINIO
PCPR_DB_NOME=$DB
# Definida por implantar.sh (imagem do commit aprovado):
PCPR_IMAGEM=
PCPR_IMAGEM_ANTERIOR=
# Recursos (ajuste à VPS — deploy/README.md §Capacidade):
PCPR_WEB_MEMORIA=1g
PCPR_WORKER_MEMORIA=1g
PCPR_DB_MEMORIA=1g
PCPR_PG_SHARED_BUFFERS=256MB
PCPR_PG_CACHE=768MB
EOF

criar "$CONF/banco.env" 0600 <<EOF
# Somente o contêiner do PostgreSQL. Superusuário do cluster (administração e backup).
POSTGRES_PASSWORD=$(segredo)
# Usadas UMA vez na criação do cluster (deploy/postgres/01-papeis.sh).
PCPR_OWNER_PASSWORD=$OWNER_SENHA
PCPR_APP_PASSWORD=$APP_SENHA
EOF

criar "$CONF/owner.env" 0600 <<EOF
# Sobrepõe o usuário do banco nas tarefas de migração/semeadura (dono do schema).
POSTGRES_USER=pcpr_owner
POSTGRES_PASSWORD=$OWNER_SENHA
EOF

DEMO_LINHA="DEMO_MODE=false"
EXTRA=""
if [ "$APP_ENV" = preview ]; then
  EXTRA="# Homologação com dados sintéticos: HTTPS ligado (cookies Secure e redirecionamento).
PREVIEW_HTTPS=true
DJANGO_SSL_REDIRECT=true"
fi
criar "$CONF/app.env" 0600 <<EOF
# Aplicação e worker da instância $INST. NUNCA versionar. Revisado em $(date -I).
DJANGO_SETTINGS_MODULE=$SETTINGS
APP_ENV=$APP_ENV
# Entrada sem senha é proibida fora do PREVIEW de demonstração (ADR 0011).
$DEMO_LINHA
DJANGO_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')
DJANGO_ALLOWED_HOSTS=$DOMINIO
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMINIO
URL_PUBLICA=https://$DOMINIO
$EXTRA
POSTGRES_DB=$DB
POSTGRES_USER=pcpr_app
POSTGRES_PASSWORD=$APP_SENHA
# Gunicorn: (2 × vCPU) + 1 é o teto; comece com 3 e meça.
WEB_CONCURRENCY=3
WEB_TIMEOUT=120
# E-mail desligado até haver SMTP institucional autorizado.
NOTIFICACOES_POR_EMAIL=false
DEFAULT_FROM_EMAIL=nao-responda@$DOMINIO
# Integrações: simuladas até haver credenciais oficiais.
EPROTOCOLO_AMBIENTE=simulado
EPROTOCOLO_SOMENTE_LEITURA=true
# Rotas: "estimativa" (offline) por padrão; OSRM próprio/autorizado via ROTAS_PROVEDOR/ROTAS_URL.
ROTAS_PROVEDOR=estimativa
EOF

echo
echo "Instância '$INST' preparada:"
echo "  configuração: $CONF (revise app.env antes do primeiro deploy)"
echo "  dados:        $PCPR_RAIZ/$INST/dados"
echo "  backups:      $PCPR_RAIZ/$INST/backups"
echo "Próximo passo: deploy/vps/implantar.sh $INST <commit-aprovado>"
