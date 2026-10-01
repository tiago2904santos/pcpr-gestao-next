#!/usr/bin/env bash
# Ambiente PREVIEW (APP_ENV=preview + DEMO_MODE) — docs/ops/preview.md.
#
#   scripts/preview.sh subir        # Docker: constrói e sobe banco + web + worker (porta 8000)
#   scripts/preview.sh resetar      # Docker: zera o banco DEMO e recria o dataset
#   scripts/preview.sh semear       # Docker: recria o dataset (idempotente)
#   scripts/preview.sh verificar    # saúde + E2E do fluxo DEMO contra a URL (PREVIEW_URL)
#   scripts/preview.sh parar        # Docker: para tudo (dados ficam no volume)
#   scripts/preview.sh logs         # Docker: acompanha os logs
#   scripts/preview.sh local        # sem Docker: PostgreSQL local, banco pcpr_preview
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f compose.preview.yml)
URL="${PREVIEW_URL:-http://localhost:${PREVIEW_PORTA:-8000}}"

case "${1:-}" in
  subir)     "${COMPOSE[@]}" up --build -d && echo "Preview: $URL (login: deixe em branco e clique em Entrar)" ;;
  resetar)   "${COMPOSE[@]}" exec web python manage.py resetar_demo ;;
  semear)    "${COMPOSE[@]}" exec web python manage.py semear_demo ;;
  parar)     "${COMPOSE[@]}" down ;;
  logs)      "${COMPOSE[@]}" logs -f ;;
  verificar)
    curl -fsS "$URL/saude/" > /dev/null && echo "saúde OK em $URL"
    PREVIEW_URL="$URL" uv run pytest tests/e2e/test_preview_demo.py -q -p no:cacheprovider
    ;;
  local)
    export DJANGO_SETTINGS_MODULE=config.settings.preview DEMO_MODE=true
    export POSTGRES_DB="${POSTGRES_DB:-pcpr_preview}"
    export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')}"
    uv run python manage.py check --deploy --fail-level ERROR
    uv run python manage.py migrate --noinput
    uv run python manage.py semear_demo --se-vazio
    uv run python manage.py collectstatic --noinput -v0
    uv run python manage.py processar_outbox &
    trap 'kill %1' EXIT
    uv run gunicorn config.wsgi --bind "127.0.0.1:${PREVIEW_PORTA:-8000}" --workers 3
    ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
