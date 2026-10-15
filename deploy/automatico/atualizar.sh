#!/usr/bin/env bash
# Executor administrativo do PREVIEW existente; não é o fluxo de produção.
set -Eeuo pipefail
umask 077
# shellcheck source=politica.sh
. "$(dirname "$0")/politica.sh"
SHA="${1:-}"
sha_valido "$SHA" || exit 64
RAIZ=/srv/pcpr/automatico
APP=/srv/pcpr/app
REPO="$RAIZ/source"
ORIGEM=https://github.com/tiago2904santos/pcpr-gestao-next.git
URL=https://pcpr.gerenciadorviagens.tech/saude/
mkdir -p "$RAIZ/logs" "$RAIZ/work" "$RAIZ/backups"
exec 9>"$RAIZ/deploy.lock"
flock -w 300 9 || { echo 'Outra implantação está em andamento.' >&2; exit 75; }
ID="$(date -u +%Y%m%dT%H%M%S-%N)-${SHA:0:12}"
exec > >(tee -a "$RAIZ/logs/$ID.log") 2>&1
log() { printf '%s %s\n' "$(date -Is)" "$*"; }
falhar() { log "ERRO: $*"; exit 1; }
espaco() {
  local livre
  livre="$(df -Pk "$RAIZ" | awk 'NR==2 {print $4}')"
  if [[ ! "$livre" =~ ^[0-9]+$ ]]; then falhar 'Espaço livre não pôde ser medido.'; fi
  if (( livre < 5 * 1024 * 1024 )); then
    falhar 'Menos de 5 GiB livres; backups preservados, publicação bloqueada.'
  fi
}
compose() {
  local pasta="$1"; shift
  local arquivos=(-f "$pasta/compose.preview.yml" -f "$pasta/compose.dev.yml" -f "$pasta/compose.vps.yml")
  [ ! -f "$pasta/compose.release.yml" ] || arquivos+=(-f "$pasta/compose.release.yml")
  docker compose -p pcpr-preview --project-directory "$pasta" "${arquivos[@]}" "$@"
}
saude() {
  curl -fsS --retry 3 --retry-delay 2 --max-time 10 "$URL" |
    python3 -c 'import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get("status")=="ok" and r.get("banco")=="ok" else 1)'
}
PAROU=0
TROCOU=0
MIGROU=0
SUCESSO=0
BACKUP=""
recuperar() {
  local rc=$?
  trap - EXIT
  if [ "$SUCESSO" = 0 ] && [ "$PAROU" = 1 ]; then
    if [ "$MIGROU" = 1 ]; then
      compose "$APP" stop web worker || true
      log "CRÍTICO: houve tentativa de migração. Serviços parados; intervenção necessária. Backup: $BACKUP"
    else
      if [ "$TROCOU" = 1 ]; then
        compose "$APP" stop web worker || true
        mv "$APP" "$BACKUP/app-falhou"
        mv "$BACKUP/app-anterior" "$APP"
      fi
      if compose "$APP" up -d --no-deps --wait --wait-timeout 180 web worker; then
        log 'Código anterior restaurado; nenhum dado foi restaurado/apagado.'
      else
        log "CRÍTICO: reversão não ficou saudável. Backup: $BACKUP"
      fi
    fi
  fi
  if [ "$rc" != 0 ]; then log "FALHOU sha=$SHA código=$rc"; fi
  exit "$rc"
}
trap recuperar EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
log "Recebido main=$SHA"
[ "$(readlink -f "$APP")" = /srv/pcpr/app ] || falhar 'Diretório da aplicação inesperado.'
[ "$(docker exec pcpr-preview-web-1 printenv APP_ENV)" = preview ] || falhar 'Não é PREVIEW.'
[ "$(docker exec pcpr-preview-web-1 printenv DJANGO_SETTINGS_MODULE)" = config.settings.preview ] || falhar 'Settings inesperados.'
espaco
if [ ! -d "$REPO/.git" ]; then
  git clone --filter=blob:none --depth=1 --sparse "$ORIGEM" "$REPO"
  git -C "$REPO" sparse-checkout set --no-cone /Dockerfile /.dockerignore /pyproject.toml \
    /uv.lock /manage.py /compose.preview.yml /compose.dev.yml /config/ /gestao/ /templates/ /static/ /scripts/
fi
[ "$(git -C "$REPO" remote get-url origin)" = "$ORIGEM" ] || falhar 'Origem Git inesperada.'
git -C "$REPO" fetch --depth=1 origin main
ATUAL="$(git -C "$REPO" rev-parse FETCH_HEAD)"
if [ "$SHA" != "$ATUAL" ]; then
  log "DESCARTADO sha obsoleto=$SHA; main atual=$ATUAL"
  exit 0
fi
if [ "$(cat "$APP/versao-main.txt" 2>/dev/null || true)" = "$SHA" ] && saude; then
  log "JÁ PUBLICADO e saudável: $SHA"
  exit 0
fi
git -C "$REPO" checkout --detach "$SHA"
STAGE="$(mktemp -d "$RAIZ/work/${SHA:0:12}-XXXXXX")"
ARQUIVOS=(Dockerfile .dockerignore pyproject.toml uv.lock manage.py compose.preview.yml compose.dev.yml config gestao templates static scripts)
git -C "$REPO" archive "$SHA" "${ARQUIVOS[@]}" | tar -xf - -C "$STAGE"
IMAGEM="pcpr-gestao:vps-$SHA"
if ! docker image inspect "$IMAGEM" >/dev/null 2>&1; then
  # Segredos/configuração da VPS só são copiados DEPOIS do build.
  docker build --label org.opencontainers.image.revision="$SHA" -t "$IMAGEM" "$STAGE"
fi
[ "$(docker image inspect "$IMAGEM" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$SHA" ] || falhar 'Imagem sem revisão correta.'
install -m 600 "$APP/.env" "$STAGE/.env"
install -m 600 "$APP/compose.vps.yml" "$STAGE/compose.vps.yml"
printf 'services:\n  web:\n    image: %s\n    environment:\n      PREVIEW_SEMEAR: nunca\n  worker:\n    image: %s\n' "$IMAGEM" "$IMAGEM" >"$STAGE/compose.release.yml"
mapfile -t CONFIG < <(compose "$STAGE" run --rm --no-deps -T web printenv APP_ENV DJANGO_SETTINGS_MODULE POSTGRES_HOST POSTGRES_DB POSTGRES_USER </dev/null)
preview_esperado "${CONFIG[@]}" || falhar 'Novo ambiente/banco não corresponde ao PREVIEW autorizado.'
compose "$STAGE" run --rm --no-deps -T web python manage.py check </dev/null
compose "$STAGE" run --rm --no-deps -T web python manage.py migrate --plan </dev/null >"$RAIZ/logs/$ID-migracoes.txt"
PENDENTE=0
compose "$STAGE" run --rm --no-deps -T web python manage.py migrate --check </dev/null || PENDENTE=1
# Um push novo durante o build não deve iniciar uma troca já obsoleta.
git -C "$REPO" fetch --depth=1 origin main
if [ "$SHA" != "$(git -C "$REPO" rev-parse FETCH_HEAD)" ]; then
  log 'DESCARTADO: main avançou durante o build; próxima execução publicará a versão nova.'
  exit 0
fi
espaco
BACKUP="$RAIZ/backups/$ID"
mkdir "$BACKUP"
PAROU=1
compose "$APP" stop web worker
docker exec pcpr-preview-db-1 pg_dump -U pcpr_preview -d pcpr_preview -Fc >"$BACKUP/banco.dump"
test -s "$BACKUP/banco.dump"
docker exec -i pcpr-preview-db-1 pg_restore --list <"$BACKUP/banco.dump" >"$BACKUP/banco-conteudo.txt"
test -s "$BACKUP/banco-conteudo.txt"
docker run --rm --network none --user 0 --entrypoint tar \
  --mount type=volume,source=pcpr-preview_midia,target=/midia,readonly \
  --mount type=bind,source="$BACKUP",target=/backup postgres:16 -cf /backup/midia.tar -C /midia .
sha256sum "$BACKUP/banco.dump" "$BACKUP/midia.tar" >"$BACKUP/SHA256SUMS"
if [ "$PENDENTE" = 1 ]; then
  MIGROU=1
  compose "$STAGE" run --rm --no-deps -T web python manage.py migrate --noinput </dev/null
fi
mv "$APP" "$BACKUP/app-anterior"
if ! mv "$STAGE" "$APP"; then
  mv "$BACKUP/app-anterior" "$APP"
  exit 1
fi
TROCOU=1
compose "$APP" up -d --no-deps --wait --wait-timeout 180 web worker
saude
[ "$(docker inspect pcpr-preview-worker-1 --format '{{.State.Running}}')" = true ]
[ "$(docker inspect pcpr-preview-worker-1 --format '{{.RestartCount}}')" = 0 ]
printf '%s\n' "$SHA" >"$APP/versao-main.txt"
printf '%s\t%s\t%s\t%s\n' "$(date -Is)" "$SHA" "$IMAGEM" "$BACKUP" >>"$RAIZ/implantacoes.tsv"
SUCESSO=1
log "PUBLICADO sha=$SHA imagem=$IMAGEM backup=$BACKUP"
