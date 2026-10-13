# shellcheck shell=bash
# shellcheck disable=SC2034  # variáveis usadas pelos scripts que carregam este arquivo
# Funções comuns dos scripts da VPS (deploy/README.md). Carregue com:  . "$(dirname "$0")/lib.sh"
set -Eeuo pipefail
umask 027

PCPR_RAIZ="${PCPR_RAIZ:-/srv/pcpr}"          # dados, backups e registros das instâncias
PCPR_ETC="${PCPR_ETC:-/etc/pcpr}"             # configuração e segredos (0700/0600)
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # …/deploy
REPO_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"
IMAGEM_RESTIC="${PCPR_IMAGEM_RESTIC:-restic/restic:0.18.1@sha256:39d9072fb5651c80d75c7a811612eb60b4c06b32ffe87c2e9f3c7222e1797e76}"

INST=""
CONF=""

morrer() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

registrar() {
  local linha
  linha="$(date -Is) [${INST:-geral}] $*"
  printf '%s\n' "$linha" >&2
  if [ -n "$INST" ] && [ -d "$PCPR_RAIZ/$INST" ]; then
    printf '%s\n' "$linha" >>"$PCPR_RAIZ/$INST/operacoes.log"
  fi
  command -v logger >/dev/null && logger -t "pcpr-${INST:-geral}" -- "$*" || true
}

# Alerta: journal sempre; webhook se configurado em /etc/pcpr/alertas.env:
#   PCPR_ALERTA_URL=https://ntfy.sh/<tópico-secreto>   (POST texto puro — ntfy, etc.)
#   PCPR_ALERTA_FORMATO=texto|slack|discord            (slack/google chat = {"text": …})
alertar() {
  local nivel="$1"; shift
  local msg="[PCPR ${INST:-geral}] $nivel: $*"
  registrar "ALERTA $nivel: $*"
  [ -f "$PCPR_ETC/alertas.env" ] || return 0
  # shellcheck disable=SC1091
  ( set -a; . "$PCPR_ETC/alertas.env"; set +a
    [ -n "${PCPR_ALERTA_URL:-}" ] || exit 0
    case "${PCPR_ALERTA_FORMATO:-texto}" in
      slack)   corpo="$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$msg")"
               curl -fsS -m 15 -H 'Content-Type: application/json' -d "$corpo" "$PCPR_ALERTA_URL" ;;
      discord) corpo="$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$msg")"
               curl -fsS -m 15 -H 'Content-Type: application/json' -d "$corpo" "$PCPR_ALERTA_URL" ;;
      *)       curl -fsS -m 15 -H "Title: PCPR $nivel" -d "$msg" "$PCPR_ALERTA_URL" ;;
    esac >/dev/null ) || registrar "falha ao enviar alerta pelo webhook"
}

carregar_instancia() {
  INST="${1:-}"
  [[ "$INST" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || morrer "instância inválida: '${INST}' (ex.: homologacao)"
  CONF="$PCPR_ETC/$INST"
  [ -f "$CONF/instancia.env" ] || morrer "instância não preparada: $CONF/instancia.env (rode preparar-instancia.sh)"
  set -a
  # shellcheck disable=SC1091
  . "$CONF/instancia.env"
  set +a
  BACKUPS="$PCPR_RAIZ/$INST/backups"
  ESTADO="$PCPR_RAIZ/$INST/estado"
  mkdir -p "$BACKUPS/banco" "$ESTADO"
}

dc() {
  docker compose -p "pcpr-$INST" --env-file "$CONF/instancia.env" -f "$DEPLOY_DIR/compose.yml" "$@"
}

# Grava/atualiza CHAVE=valor no instancia.env (não secreto).
definir_variavel() {
  local chave="$1" valor="$2" arq="$CONF/instancia.env"
  if grep -q "^${chave}=" "$arq"; then
    sed -i "s|^${chave}=.*|${chave}=${valor}|" "$arq"
  else
    printf '%s=%s\n' "$chave" "$valor" >>"$arq"
  fi
}

sql_valor() {  # executa SQL no banco da instância como superusuário do cluster; 1 valor
  dc exec -T db psql -U postgres -d "$PCPR_DB_NOME" -XAtq -v ON_ERROR_STOP=1 -c "$1"
}

trava() {  # impede duas operações concorrentes na mesma instância
  exec 9>"$PCPR_RAIZ/$INST/.trava"
  flock -n 9 || morrer "outra operação já está em andamento em $INST"
}

# Dados reais? Decide pela configuração que a aplicação usa de fato (app.env), não pelo nome
# da instância: só homologação com config.settings.preview e APP_ENV=preview é sintética.
# Na dúvida (arquivo ilegível, valor ausente), trata como real.
dados_reais() {
  local env settings
  env="$(sed -n 's/^APP_ENV=//p' "$CONF/app.env" 2>/dev/null | tail -1)"
  settings="$(sed -n 's/^DJANGO_SETTINGS_MODULE=//p' "$CONF/app.env" 2>/dev/null | tail -1)"
  [ "$env" != preview ] || [ "$settings" != config.settings.preview ]
}

recusar_dados_reais() {  # recusar_dados_reais <motivo>
  ! dados_reais || morrer "$1 (instância $INST usa dados reais: APP_ENV/settings fora de preview)"
}
