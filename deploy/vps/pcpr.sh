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
#   pcpr.sh <instância> reverter [<dump-pre-implantacao> --confirmo-sobrescrever-<instância>]
#                                          volta web/worker para a imagem anterior; se a versão
#                                          ativa migrou, exige o dump (para, restaura e só então sobe)
#   pcpr.sh <instância> restaurar-banco <dump> --confirmo-sobrescrever-<instância>
#                                          SUBSTITUI o banco da instância pelo dump
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"
CMD="${2:-status}"; shift 2 || true
export PCPR_IMAGEM="${PCPR_IMAGEM:?instância sem imagem implantada}"

# Antes de apagar qualquer coisa: o arquivo é um dump legível e, se houver, confere com o
# SHA-256 gravado pelo backup.sh (arquivo truncado/trocado é recusado com o banco intacto).
validar_dump() {  # validar_dump <dump> <confirmação>
  [ -f "$1" ] || morrer "dump não encontrado: $1"
  [ "$2" = "--confirmo-sobrescrever-$INST" ] || \
    morrer "operação destrutiva: repita com --confirmo-sobrescrever-$INST"
  dc up -d --wait db
  dc exec -T db pg_restore --list <"$1" >/dev/null || morrer "dump ilegível: $1"
  if [ -f "$1.sha256" ]; then
    ( cd "$(dirname "$1")" && grep -F "  $(basename "$1")" "$(basename "$1").sha256" | sha256sum -c --quiet ) \
      || morrer "SHA-256 do dump não confere: $1"
  else
    registrar "aviso: $1 sem .sha256 (só a estrutura do dump foi conferida)"
  fi
}

# Escritas param ANTES do backup de segurança: tudo o que foi gravado até aqui fica nele.
parar_e_guardar() {
  dc stop web worker
  "$DEPLOY_DIR/vps/backup.sh" "$INST" --motivo antes-de-restaurar --sem-trava || {
    dc up -d web worker; morrer "backup de segurança falhou: nada foi restaurado"; }
}

# Troca o banco pelo dump (web e worker já parados) e confere os anexos que ele referencia:
# um dump antigo pode apontar para um arquivo já substituído (o Coffee apaga o anterior).
# Faltando algum, web e worker FICAM PARADOS e o alerta diz como recuperar do restic.
substituir_banco() {  # substituir_banco <dump>
  registrar "RESTAURANDO banco de $INST a partir de $(basename "$1")"
  dc exec -T db psql -U postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE \"$PCPR_DB_NOME\" WITH (FORCE)" \
    -c "CREATE DATABASE \"$PCPR_DB_NOME\" OWNER pcpr_owner" \
    -c "REVOKE ALL ON DATABASE \"$PCPR_DB_NOME\" FROM PUBLIC" \
    -c "GRANT CONNECT, TEMPORARY ON DATABASE \"$PCPR_DB_NOME\" TO pcpr_app" \
    -c "GRANT CONNECT ON DATABASE \"$PCPR_DB_NOME\" TO pcpr_leitura"
  dc exec -T db pg_restore -U postgres -d "$PCPR_DB_NOME" --exit-on-error <"$1"
  local ausentes
  ausentes="$(anexos_ausentes "$PCPR_DADOS/midia" sql_valor)"
  if [ -n "$ausentes" ]; then
    sed 's/^/  faltando: /' <<<"$ausentes" >&2
    alertar CRITICO "banco restaurado, mas $(wc -l <<<"$ausentes") anexo(s) que ele referencia não \
estão em dados/midia: web e worker seguem PARADOS. Recupere-os do snapshot do mesmo backup \
(restic restore <snapshot> --include /dados/midia/<caminho>) e suba com: pcpr.sh $INST compose up -d web worker"
    exit 1
  fi
}

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
    # Sem migração na versão ativa: troca só a imagem (banco intacto). Com migração, a imagem
    # anterior não pode rodar contra o schema novo: só junto com o dump pré-implantação, numa
    # operação única (para tudo → restaura o banco → sobe a imagem anterior).
    trava
    [ -n "${PCPR_IMAGEM_ANTERIOR:-}" ] || morrer "não há imagem anterior registrada"
    MIGROU="$(cat "$ESTADO/migracoes-versao-ativa" 2>/dev/null || echo 0)"
    if [ "$MIGROU" != 0 ]; then
      DUMP="${1:-}"; CONFIRMA="${2:-}"
      [ -n "$DUMP" ] || morrer "a versão ativa aplicou $MIGROU migração(ões): reverta junto com o \
banco — pcpr.sh $INST reverter <dump-pre-implantacao> --confirmo-sobrescrever-$INST \
(perde o que foi gravado depois do dump)"
      validar_dump "$DUMP" "$CONFIRMA"
      parar_e_guardar
      substituir_banco "$DUMP"
    fi
    registrar "revertendo $PCPR_IMAGEM → $PCPR_IMAGEM_ANTERIOR${DUMP:+ com o banco de $(basename "$DUMP")}"
    definir_variavel PCPR_IMAGEM "$PCPR_IMAGEM_ANTERIOR"
    definir_variavel PCPR_IMAGEM_ANTERIOR "$PCPR_IMAGEM"
    PCPR_IMAGEM="$PCPR_IMAGEM_ANTERIOR" dc up -d --wait --wait-timeout 240 web worker
    docker image inspect -f '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
      "$PCPR_IMAGEM_ANTERIOR" >"$ESTADO/versao-ativa"
    echo 0 >"$ESTADO/migracoes-versao-ativa"
    PCPR_IMAGEM="$PCPR_IMAGEM_ANTERIOR" "$DEPLOY_DIR/vps/smoke.sh" "$INST"
    ;;
  restaurar-banco)
    trava
    DUMP="${1:-}"
    validar_dump "$DUMP" "${2:-}"
    parar_e_guardar
    substituir_banco "$DUMP"
    # O dump pode ser anterior a migrações da imagem atual: leva o banco até ela antes de subir
    # (as entradas de web/worker não migram de propósito).
    dc run --rm -T migrar || { alertar CRITICO "migração após restaurar $(basename "$DUMP") falhou: \
web e worker seguem PARADOS"; exit 1; }
    dc up -d --wait web worker
    "$DEPLOY_DIR/vps/smoke.sh" "$INST"
    registrar "banco restaurado de $(basename "$DUMP")"
    ;;
  *) morrer "comando desconhecido: $CMD (veja o cabeçalho de $0)" ;;
esac
