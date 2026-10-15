#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=politica.sh
. /usr/local/lib/pcpr-main/politica.sh
sha="$(sha_do_comando "${SSH_ORIGINAL_COMMAND:-}")" || {
  echo 'Comando recusado: esta chave permite somente deploy de um SHA do main.' >&2
  exit 64
}
exec /usr/local/lib/pcpr-main/atualizar.sh "$sha"
