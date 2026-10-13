#!/usr/bin/env bash
# Implanta um COMMIT IMUTÁVEL do produto numa instância (deploy/README.md §Implantação).
#
#   deploy/vps/implantar.sh <instância> <sha-40> [--semear] [--sem-backup]
#
# Fluxo: 1 valida versão → 2 constrói imagens → 3 verificações → 4 backup → 5 migrações →
#        6 troca a versão → 7 sobe serviços → 8 saúde → 9 smoke → 10 registra versão ativa.
# Nunca aceita nome de branch. Em PRODUÇÃO o commit precisa constar em
# /etc/pcpr/producao/aprovados.txt (autorização registrada antes da janela).
. "$(dirname "$0")/lib.sh"

carregar_instancia "${1:-}"
ANTERIOR="${PCPR_IMAGEM:-}"
SHA="${2:-}"; shift 2 || true
SEMEAR=0; SEM_BACKUP=0
for arg in "$@"; do
  case "$arg" in
    --semear) SEMEAR=1 ;;
    --sem-backup) SEM_BACKUP=1 ;;
    *) morrer "opção desconhecida: $arg" ;;
  esac
done
trava

# 1. Versão --------------------------------------------------------------------------------
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || morrer "informe o commit COMPLETO (40 hex); branches não são aceitas"
git -C "$REPO_DIR" fetch --quiet origin '+refs/heads/*:refs/remotes/origin/*' --tags || \
  registrar "aviso: fetch falhou; usando objetos locais"
git -C "$REPO_DIR" cat-file -e "${SHA}^{commit}" 2>/dev/null || morrer "commit $SHA não existe no repositório"
if [ "$INST" = producao ]; then
  grep -qx "$SHA" "$CONF/aprovados.txt" 2>/dev/null || \
    morrer "commit não aprovado para produção (adicione a $CONF/aprovados.txt após a autorização)"
  [ "$SEM_BACKUP" = 0 ] || morrer "--sem-backup é proibido em produção"
  [ "$SEMEAR" = 0 ] || morrer "--semear é proibido em produção"
fi
INFRA="$(git -C "$REPO_DIR" rev-parse HEAD)"
git -C "$REPO_DIR" diff --quiet HEAD -- deploy || morrer "deploy/ com mudanças locais não commitadas"
registrar "implantação iniciada: produto=$SHA infra=$INFRA ($(git -C "$REPO_DIR" log -1 --format='%cs %s' "$SHA"))"

# 2. Imagens -------------------------------------------------------------------------------
BASE="pcpr-gestao:$SHA"
NOVA="pcpr-gestao-implantacao:${SHA:0:12}-${INFRA:0:12}"
if ! docker image inspect "$BASE" >/dev/null 2>&1; then
  registrar "construindo $BASE a partir de git archive (Dockerfile do produto, sem alterações)"
  git -C "$REPO_DIR" archive --format=tar "$SHA" | docker build -q -t "$BASE" - >/dev/null
fi
docker build -q -t "$NOVA" --build-arg "BASE=$BASE" --build-arg "PRODUTO_COMMIT=$SHA" \
  --build-arg "INFRA_COMMIT=$INFRA" "$DEPLOY_DIR/docker" >/dev/null
registrar "imagem pronta: $NOVA"
# A partir daqui todo comando compose interpola a nova imagem; o que está no ar só muda no
# passo 7 (os contêineres web/worker em execução não são recriados antes disso).
export PCPR_IMAGEM="$NOVA"

# 3. Verificações (sem tocar no que está no ar) ---------------------------------------------
dc run --rm --no-deps -T --entrypoint pcpr-entrypoint tarefa verificar \
  || morrer "check --deploy reprovou a nova versão"

# 4. Backup --------------------------------------------------------------------------------
PRIMEIRA=0
[ -f "$PCPR_DADOS/postgres/PG_VERSION" ] || PRIMEIRA=1
dc up -d --wait db
if [ "$PRIMEIRA" = 1 ]; then
  registrar "primeira implantação: banco ainda não existe, sem backup prévio"
elif [ "$SEM_BACKUP" = 0 ]; then
  "$DEPLOY_DIR/vps/backup.sh" "$INST" --motivo pre-implantacao --sem-trava || morrer "backup prévio falhou"
fi

# 5. Migrações ------------------------------------------------------------------------------
MIGRACOES_ANTES="$(sql_valor "SELECT count(*) FROM django_migrations" 2>/dev/null || echo 0)"
dc run --rm -T migrar || morrer "migração falhou — serviços seguem na versão anterior; veja deploy/README.md §Reversão"
MIGRACOES_DEPOIS="$(sql_valor "SELECT count(*) FROM django_migrations")"
registrar "migrações aplicadas: $((MIGRACOES_DEPOIS - MIGRACOES_ANTES))"

# 6–7. Troca de versão e subida ------------------------------------------------------------
definir_variavel PCPR_IMAGEM_ANTERIOR "$ANTERIOR"
definir_variavel PCPR_IMAGEM "$NOVA"
if ! dc up -d --wait --wait-timeout 240 --remove-orphans db web worker; then
  FALHA="serviços não ficaram saudáveis"
fi

if [ "$SEMEAR" = 1 ] && [ -z "${FALHA:-}" ]; then
  registrar "semeando dataset sintético (só PREVIEW/homologação; o produto recusa nos demais)"
  dc run --rm -T semear || FALHA="semear_demo falhou"
fi

# 8–9. Saúde e smoke -----------------------------------------------------------------------
if [ -z "${FALHA:-}" ]; then
  "$DEPLOY_DIR/vps/smoke.sh" "$INST" || FALHA="smoke test reprovou"
fi

if [ -n "${FALHA:-}" ]; then
  alertar CRITICO "implantação de ${SHA:0:12} falhou: $FALHA"
  if [ -n "$ANTERIOR" ] && [ "$MIGRACOES_DEPOIS" = "$MIGRACOES_ANTES" ]; then
    registrar "sem migrações novas: voltando automaticamente para $ANTERIOR"
    definir_variavel PCPR_IMAGEM "$ANTERIOR"
    definir_variavel PCPR_IMAGEM_ANTERIOR "$NOVA"
    PCPR_IMAGEM="$ANTERIOR" dc up -d --wait --wait-timeout 240 web worker || true
  else
    registrar "houve migração (ou não há versão anterior): reversão exige decisão humana — deploy/README.md §Reversão"
  fi
  exit 1
fi

# 10. Registro -----------------------------------------------------------------------------
printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$SHA" "$INFRA" "$NOVA" "${SUDO_USER:-$(id -un)}" \
  >>"$PCPR_RAIZ/$INST/implantacoes.tsv"
echo "$SHA" >"$ESTADO/versao-ativa"
registrar "implantação concluída: $NOVA (anterior: ${ANTERIOR:-nenhuma})"

# Limpeza: mantém a imagem atual e a anterior de TODAS as instâncias (reversão sem rebuild).
MANTER="$(sed -n 's/^PCPR_IMAGEM\(_ANTERIOR\)\{0,1\}=//p' "$PCPR_ETC"/*/instancia.env | sort -u)"
for img in $(docker image ls --format '{{.Repository}}:{{.Tag}}' pcpr-gestao-implantacao); do
  grep -qx "$img" <<<"$MANTER" || docker image rm "$img" >/dev/null 2>&1 || true
done
for img in $(docker image ls --format '{{.Repository}}:{{.Tag}}' pcpr-gestao); do
  curto="${img#pcpr-gestao:}"; curto="${curto:0:12}"
  grep -q "^pcpr-gestao-implantacao:${curto}-" <<<"$MANTER" || docker image rm "$img" >/dev/null 2>&1 || true
done
