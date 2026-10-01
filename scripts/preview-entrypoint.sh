#!/bin/sh
# Entrada do contêiner do PREVIEW (docs/ops/preview.md).
#   web    → checks, migrações, dataset DEMO na primeira subida, gunicorn
#   worker → worker da outbox (PDFs)
set -eu

# Sem chave fornecida, gera uma aleatória (sessões caem ao reiniciar — aceitável no preview).
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
  export DJANGO_SECRET_KEY
fi

case "${1:-web}" in
  web)
    # Falha aqui se DEMO_MODE estiver fora do PREVIEW ou o banco não for de demonstração.
    python manage.py check --deploy --fail-level ERROR
    python manage.py migrate --noinput
    if [ "${PREVIEW_SEMEAR:-se-vazio}" = "se-vazio" ]; then
      python manage.py semear_demo --se-vazio
    fi
    exec gunicorn config.wsgi --bind 0.0.0.0:8000 --workers "${WEB_CONCURRENCY:-3}" \
      --access-logfile - --forwarded-allow-ips "*"
    ;;
  worker)
    exec python manage.py processar_outbox
    ;;
  *)
    exec "$@"
    ;;
esac
