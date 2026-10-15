#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/politica.sh"
sha=8757f249c17ceaf1f897bc10593f9550f49f057b
sha_valido "$sha"
[ "$(sha_do_comando "deploy $sha")" = "$sha" ]
for invalido in '' main '../main' "$sha;id" "${sha^^}"; do
  if sha_valido "$invalido"; then exit 1; fi
done
for comando in id bash "deploy main" "deploy $sha; id" "deploy  $sha" "deploy $sha " "deploy $sha"$'\nid'; do
  if sha_do_comando "$comando" >/dev/null; then exit 1; fi
done
preview_esperado preview config.settings.preview db pcpr_preview pcpr_preview
if preview_esperado production config.settings.production db pcpr_preview pcpr_preview; then exit 1; fi
if preview_esperado preview config.settings.preview remoto pcpr_preview pcpr_preview; then exit 1; fi
if preview_esperado preview config.settings.preview db institucional pcpr_preview; then exit 1; fi
printf 'Política: SHA, comando restrito e bloqueio de produção/banco remoto OK.\n'
