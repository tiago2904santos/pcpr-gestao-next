#!/usr/bin/env bash
# Operação do dia a dia de uma instância (deploy/README.md §Operação).
#
#   pcpr.sh <instância> status             serviços, versão ativa e verificações
#   pcpr.sh <instância> logs [serviço]     últimos logs (web | worker | db)
#   pcpr.sh <instância> reiniciar          reinicia web e worker (banco intacto)
#   pcpr.sh <instância> rotinas            verificar_auditoria + rotinas diárias (timer)
#   pcpr.sh <instância> senha <login>      define a senha de um usuário (interativo)
#   pcpr.sh <instância> manage <cmd…>      qualquer manage.py como pcpr_app
#   pcpr.sh <instância> compose <args…>    docker compose da instância
#   pcpr.sh <instância> reverter           volta web/worker para a imagem anterior
#                                          (só se não houve migração — ver README §Reversão)
#   pcpr.sh <instância> restaurar-banco <dump> --confirmo-sobrescrever-<instância>
#                                          SUBSTITUI o banco da instância pelo dump
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"
CMD="${2:-status}"; shift 2 || true
export PCPR_IMAGEM="${PCPR_IMAGEM:?instância sem imagem implantada}"

case "$CMD" in
  status)
    dc ps
    echo "versão ativa: $(cat "$ESTADO/versao-ativa" 2>/dev/null || echo '?')  imagem: $PCPR_IMAGEM"
    tail -n 3 "$PCPR_RAIZ/$INST/implantacoes.tsv" 2>/dev/null || true
    "$DEPLOY_DIR/vps/monitorar.sh" "$INST" --mostrar || true
    ;;
  logs) dc logs --tail "${LINHAS:-200}" --timestamps "$@" ;;
  reiniciar) dc up -d --wait --force-recreate web worker; registrar "web/worker reiniciados" ;;
  rotinas)
    if dc run --rm -T tarefa verificar_auditoria; then
      date -Is >"$ESTADO/auditoria-ok"
    else
      alertar CRITICO "cadeia de auditoria QUEBRADA ou verificação falhou"; exit 1
    fi
    dc run --rm -T tarefa rodar_rotinas_diarias || { alertar AVISO "rotinas diárias falharam"; exit 1; }
    ;;
  senha) [ -n "${1:-}" ] || morrer "uso: pcpr.sh $INST senha <login>"; dc run --rm tarefa changepassword "$1" ;;
  manage) dc run --rm -T tarefa "$@" ;;
  compose) dc "$@" ;;
  reverter)
    trava
    [ -n "${PCPR_IMAGEM_ANTERIOR:-}" ] || morrer "não há imagem anterior registrada"
    registrar "revertendo $PCPR_IMAGEM → $PCPR_IMAGEM_ANTERIOR (banco inalterado)"
    definir_variavel PCPR_IMAGEM "$PCPR_IMAGEM_ANTERIOR"
    definir_variavel PCPR_IMAGEM_ANTERIOR "$PCPR_IMAGEM"
    PCPR_IMAGEM="$PCPR_IMAGEM_ANTERIOR" dc up -d --wait --wait-timeout 240 web worker
    docker image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
      "$PCPR_IMAGEM_ANTERIOR" >"$ESTADO/versao-ativa"
    "$DEPLOY_DIR/vps/smoke.sh" "$INST"
    ;;
  restaurar-banco)
    trava
    DUMP="${1:-}"; CONFIRMA="${2:-}"
    [ -f "$DUMP" ] || morrer "dump não encontrado: $DUMP"
    [ "$CONFIRMA" = "--confirmo-sobrescrever-$INST" ] || \
      morrer "operação destrutiva: repita com --confirmo-sobrescrever-$INST"
    # Antes de apagar qualquer coisa: o arquivo é um dump legível e, se houver, confere com o
    # SHA-256 gravado pelo backup.sh (arquivo truncado/trocado é recusado com o banco intacto).
    dc up -d --wait db
    dc exec -T db pg_restore --list <"$DUMP" >/dev/null || morrer "dump ilegível: $DUMP"
    if [ -f "$DUMP.sha256" ]; then
      ( cd "$(dirname "$DUMP")" && grep -F "  $(basename "$DUMP")" "$(basename "$DUMP").sha256" | sha256sum -c --quiet ) \
        || morrer "SHA-256 do dump não confere: $DUMP"
    else
      registrar "aviso: $DUMP sem .sha256 (só a estrutura do dump foi conferida)"
    fi
    "$DEPLOY_DIR/vps/backup.sh" "$INST" --motivo antes-de-restaurar --sem-trava
    registrar "RESTAURANDO banco de $INST a partir de $(basename "$DUMP")"
    dc stop web worker
    dc exec -T db psql -U postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE \"$PCPR_DB_NOME\" WITH (FORCE)" \
      -c "CREATE DATABASE \"$PCPR_DB_NOME\" OWNER pcpr_owner" \
      -c "REVOKE ALL ON DATABASE \"$PCPR_DB_NOME\" FROM PUBLIC" \
      -c "GRANT CONNECT, TEMPORARY ON DATABASE \"$PCPR_DB_NOME\" TO pcpr_app" \
      -c "GRANT CONNECT ON DATABASE \"$PCPR_DB_NOME\" TO pcpr_leitura"
    dc exec -T db pg_restore -U postgres -d "$PCPR_DB_NOME" --exit-on-error <"$DUMP"
    dc up -d --wait web worker
    "$DEPLOY_DIR/vps/smoke.sh" "$INST"
    registrar "banco restaurado de $(basename "$DUMP")"
    ;;
  *) morrer "comando desconhecido: $CMD (veja o cabeçalho de $0)" ;;
esac
