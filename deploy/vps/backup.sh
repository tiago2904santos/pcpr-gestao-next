#!/usr/bin/env bash
# Backup de uma instância: dump lógico do PostgreSQL (local, validado) + cópia EXTERNA,
# criptografada e deduplicada (restic) do dump e dos documentos.
#
#   deploy/vps/backup.sh <instância> [--motivo diario|pre-implantacao|manual] [--sem-trava]
#   deploy/vps/backup.sh <instância> --iniciar-repositorio     # uma vez, cria o repositório
#
# Cópia externa: $CONF/backup.env (0600), por exemplo
#   RESTIC_REPOSITORY=sftp:backup@outro-servidor:/pcpr/homologacao   # ou s3:/b2:/rclone:
#   RESTIC_PASSWORD=<senha longa — guarde também FORA da VPS, sem ela não há restauração>
#   (+ credenciais do destino, ex.: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY ou B2_ACCOUNT_*)
# Sem backup.env o backup local ainda roda, mas é tratado como DEGRADADO (alerta).
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"; shift || true
MOTIVO=manual; TRAVAR=1; INICIAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --motivo) MOTIVO="$2"; shift 2 ;;
    --sem-trava) TRAVAR=0; shift ;;
    --iniciar-repositorio) INICIAR=1; shift ;;
    *) morrer "opção desconhecida: $1" ;;
  esac
done
[ "$TRAVAR" = 1 ] && trava

RETENCAO_LOCAL_DIAS="${PCPR_BACKUP_RETENCAO_LOCAL_DIAS:-7}"
CACHE="$PCPR_RAIZ/.cache-restic"; mkdir -p "$CACHE"

restic() {  # restic em contêiner fixado; repositório e senha só do backup.env
  docker run --rm -i --env-file "$CONF/backup.env" --hostname "pcpr-$INST" \
    -v "$CACHE:/cache" -v "$BACKUPS/banco:/dados/banco:ro" -v "$PCPR_DADOS/midia:/dados/midia:ro" \
    "$IMAGEM_RESTIC" --cache-dir /cache "$@"
}

if [ "$INICIAR" = 1 ]; then
  [ -f "$CONF/backup.env" ] || morrer "crie $CONF/backup.env primeiro"
  restic init
  registrar "repositório restic iniciado"
  exit 0
fi

falhou() { rm -f "${ARQ:-}.parcial"; alertar CRITICO "backup ($MOTIVO) falhou na linha $1"; }
trap 'falhou $LINENO' ERR

export PCPR_IMAGEM="${PCPR_IMAGEM:-indefinida}"   # só para interpolar o compose
TS="$(date +%Y%m%dT%H%M%S)"
ARQ="$BACKUPS/banco/${PCPR_DB_NOME}-${TS}-${MOTIVO}.dump"

# 1. Dump consistente (snapshot MVCC) pelo superusuário do cluster, gravado pelo host.
registrar "backup ($MOTIVO): dump de $PCPR_DB_NOME"
dc exec -T db pg_dump -U postgres -d "$PCPR_DB_NOME" -Fc -Z 6 >"$ARQ.parcial"
dc exec -T db pg_dumpall -U postgres --globals-only --no-role-passwords >"$ARQ.papeis.sql"
mv "$ARQ.parcial" "$ARQ"

# 2. Validação: o arquivo precisa ser legível pelo pg_restore.
OBJETOS="$(dc exec -T db pg_restore --list <"$ARQ" | grep -vc '^;')"
[ "$OBJETOS" -gt 50 ] || { registrar "dump suspeito: só $OBJETOS objetos"; false; }
( cd "$BACKUPS/banco" && sha256sum "$(basename "$ARQ")" "$(basename "$ARQ").papeis.sql" >"$(basename "$ARQ").sha256" )
TAMANHO="$(du -h "$ARQ" | cut -f1)"
registrar "dump ok: $(basename "$ARQ") ($TAMANHO, $OBJETOS objetos)"

# 3. Retenção local (somente arquivos deste script nesta pasta).
find "$BACKUPS/banco" -maxdepth 1 -type f -name "${PCPR_DB_NOME}-*" -mtime "+$RETENCAO_LOCAL_DIAS" -delete
find "$BACKUPS/banco" -maxdepth 1 -type f -name "${PCPR_DB_NOME}-*.parcial" -mmin +60 -delete

# 4. Cópia externa: dumps + documentos. O dump é feito ANTES dos documentos: todo PDF
#    referenciado pelo banco já existe no disco (arquivos emitidos não são reescritos).
if [ -f "$CONF/backup.env" ]; then
  restic backup --tag "$INST" --tag "$MOTIVO" /dados/banco /dados/midia --quiet
  if [ "$MOTIVO" = diario ]; then
    restic forget --tag "$INST" --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune --quiet
    # Verificação leve diária; amostra de 5% dos dados aos domingos.
    if [ "$(date +%u)" = 7 ]; then restic check --read-data-subset=5% >/dev/null; else restic check >/dev/null; fi
  fi
  date -Is >"$ESTADO/backup-externo-ok"
  registrar "cópia externa ok ($(sed -n 's/^RESTIC_REPOSITORY=\([a-z0-9]*\):.*/\1/p' "$CONF/backup.env"))"
else
  alertar AVISO "backup externo NÃO configurado ($CONF/backup.env ausente): só há cópia local na VPS"
fi
date -Is >"$ESTADO/backup-ok"
echo "$ARQ" >"$ESTADO/ultimo-dump"
registrar "backup ($MOTIVO) concluído"
