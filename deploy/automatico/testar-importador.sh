#!/usr/bin/env bash
set -euo pipefail
# Carrega somente os helpers, sem executar o deploy; Docker/Compose são simulados.
# shellcheck disable=SC1090
. <(sed -n '/^servicos_aplicacao() {/,/^PAROU=0/p' "$(dirname "$0")/atualizar.sh" | sed '$d')
compose() {
  local versao="$1"; shift
  if [ "$*" = 'config --services' ]; then
    printf 'db\nweb\nworker\n'
    if [ "$versao" = nova ]; then printf 'importador\n'; fi
    return 0
  fi
  printf '%s\n' "$*"
}
[ "$(operar_aplicacao antiga stop)" = 'stop web worker' ]
[ "$(operar_aplicacao nova stop)" = 'stop web worker importador' ]
[ "$(operar_aplicacao nova up -d --no-deps --wait)" = 'up -d --no-deps --wait web worker importador' ]
CONECTADO=false
INTERNA=true
docker() {
  case "$1 $2" in
    'network inspect')
      if [ "$#" = 3 ]; then return 0; fi
      case "$*" in
        *Internal*) printf '%s\n' "$INTERNA" ;;
        *) printf 'pcpr-preview\n' ;;
      esac ;;
    'inspect pcpr-preview-db-1') printf '%s\n' "$CONECTADO" ;;
    'network connect') printf '%s\n' "$*" ;;
    *) return 97 ;;
  esac
}
[ -z "$(preparar_importador antiga)" ]
[ "$(preparar_importador nova)" = 'network connect --alias db pcpr-preview_processamento pcpr-preview-db-1' ]
CONECTADO=true
[ -z "$(preparar_importador nova)" ]
INTERNA=false
if preparar_importador nova; then exit 1; fi
printf 'Importador: serviços por versão, parada conjunta, rede interna e conexão idempotente OK.\n'
