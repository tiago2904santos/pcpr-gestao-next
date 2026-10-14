#!/bin/sh
# Entrada dos contêineres de HOMOLOGAÇÃO / PRODUÇÃO (deploy/compose.yml).
# Diferente do PREVIEW (scripts/preview-entrypoint.sh): não gera chave, não semeia dados e
# não migra sozinho — migração é um passo explícito do procedimento (`migrar`).
#
#   web      → check --deploy e gunicorn
#   worker   → worker da outbox (PDFs e demais assinantes)
#   migrar   → check, migrate e privilégios pós-migração (rodar com o papel dono do schema)
#   verificar → check --deploy da implantação (deploy/docker/verificar.py)
#   tarefa … → qualquer manage.py (ex.: `tarefa verificar_auditoria`)
set -eu

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  echo "DJANGO_SECRET_KEY ausente: defina no arquivo de ambiente da instância." >&2
  exit 64
fi
# Caches de fontes (fontconfig/WeasyPrint) fora da raiz somente leitura.
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/cache}"
mkdir -p "$XDG_CACHE_HOME"

case "${1:-web}" in
  web)
    python /opt/pcpr/verificar.py
    # Só o proxy alcança a porta (127.0.0.1 / rede interna do compose): por isso os
    # cabeçalhos X-Forwarded-* recebidos são confiáveis — ver deploy/README.md §Proxy.
    exec gunicorn config.wsgi \
      --bind 0.0.0.0:8000 \
      --workers "${WEB_CONCURRENCY:-3}" \
      --threads "${WEB_THREADS:-1}" \
      --timeout "${WEB_TIMEOUT:-120}" \
      --graceful-timeout 30 \
      --keep-alive 5 \
      --max-requests 1000 --max-requests-jitter 100 \
      --worker-tmp-dir /dev/shm \
      --forwarded-allow-ips "*" \
      --access-logfile - --error-logfile - \
      --config /opt/pcpr/gunicorn_conf.py
    ;;
  worker)
    python manage.py check --fail-level ERROR
    exec python manage.py processar_outbox
    ;;
  migrar)
    python /opt/pcpr/verificar.py
    python manage.py migrate --noinput
    python /opt/pcpr/pos_migracao.py
    python manage.py showmigrations --plan | tail -n 3
    ;;
  verificar)
    exec python /opt/pcpr/verificar.py
    ;;
  tarefa)
    shift
    exec python manage.py "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
