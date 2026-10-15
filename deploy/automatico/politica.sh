# shellcheck shell=bash
sha_valido() { [[ "${1:-}" =~ ^[0-9a-f]{40}$ ]]; }
sha_do_comando() {
  [[ "${1:-}" =~ ^deploy\ ([0-9a-f]{40})$ ]] || return 64
  printf '%s\n' "${BASH_REMATCH[1]}"
}
preview_esperado() {
  [ "${1:-}" = preview ] && [ "${2:-}" = config.settings.preview ] &&
    [ "${3:-}" = db ] && [ "${4:-}" = pcpr_preview ] && [ "${5:-}" = pcpr_preview ]
}
