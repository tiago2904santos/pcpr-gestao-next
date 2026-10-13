#!/usr/bin/env bash
# Teste de restauração em ambiente ISOLADO (não toca na instância em execução).
#
#   deploy/vps/restaurar-teste.sh <instância> [--origem externo|local]
#
# externo (padrão quando há backup.env): baixa o snapshot mais recente do restic — prova a
#          recuperação após perda total da VPS.
# local:   usa o último dump local e a pasta de documentos atual.
# Verifica: pg_restore sem erros, contagens das tabelas principais, cadeia de hash da
# auditoria (verificar_auditoria do próprio produto) e o SHA-256 de cada PDF emitido.
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"; shift || true
ORIGEM=""
while [ $# -gt 0 ]; do
  case "$1" in --origem) ORIGEM="$2"; shift 2 ;; *) morrer "opção desconhecida: $1" ;; esac
done
[ -n "$ORIGEM" ] || { [ -f "$CONF/backup.env" ] && ORIGEM=externo || ORIGEM=local; }
case "$ORIGEM" in externo|local) ;; *) morrer "--origem inválida: '$ORIGEM' (externo|local)" ;; esac
export PCPR_IMAGEM="${PCPR_IMAGEM:?instância sem imagem implantada}"

TS="$(date +%Y%m%dT%H%M%S)"
TRAB="$PCPR_RAIZ/.restauracao-teste/$INST-$TS"
NOME="pcpr-restauracao-$INST-$TS"
REDE="$NOME"
IMAGEM_PG="$(dc config --images | grep -m1 postgres)"
install -d -m 0700 "$TRAB"
limpar() {
  docker rm -f "$NOME" >/dev/null 2>&1 || true
  docker network rm "$REDE" >/dev/null 2>&1 || true
  rm -rf "$TRAB"
}
# Qualquer saída com erro alerta — inclusive as recusas explícitas (`morrer` sai sem passar
# pelo ERR): um teste mensal reprovado não pode ficar mudo.
LINHA_ERRO=""
trap 'LINHA_ERRO=$LINENO' ERR
encerrar() {
  local st=$?
  limpar
  [ "$st" = 0 ] || alertar CRITICO "teste de restauração ($ORIGEM) FALHOU${LINHA_ERRO:+ na linha $LINHA_ERRO} (saída $st)"
}
trap encerrar EXIT

# 1. Obter os dados
if [ "$ORIGEM" = externo ]; then
  CACHE="$PCPR_RAIZ/.cache-restic"; mkdir -p "$CACHE"
  docker run --rm --env-file "$CONF/backup.env" -v "$CACHE:/cache" -v "$TRAB:/restauro" \
    "$IMAGEM_RESTIC" --cache-dir /cache restore latest --tag "$INST" --target /restauro --quiet
  DUMP="$(ls -1t "$TRAB"/dados/banco/*.dump | head -1)"
  MIDIA="$TRAB/dados/midia"
else
  DUMP="$(cat "$ESTADO/ultimo-dump")"
  MIDIA="$PCPR_DADOS/midia"
fi
[ -f "$DUMP" ] || morrer "dump não encontrado"
( cd "$(dirname "$DUMP")" && sha256sum -c --quiet "$(basename "$DUMP").sha256" ) \
  || morrer "SHA-256 do dump não confere"
registrar "restauração-teste ($ORIGEM): $(basename "$DUMP")"

# 2. PostgreSQL efêmero, sem acesso à internet nem à rede da instância
docker network create --internal "$REDE" >/dev/null
SENHA="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
docker run -d --name "$NOME" --network "$REDE" --network-alias db --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_PASSWORD="$SENHA" -e POSTGRES_DB=restauracao_demo "$IMAGEM_PG" >/dev/null
# Por TCP: o servidor temporário da inicialização da imagem só escuta no socket Unix e logo
# reinicia; esperar pelo socket deixava o psql seguinte pegar esse reinício.
for _ in $(seq 60); do docker exec "$NOME" pg_isready -h 127.0.0.1 -U postgres -d restauracao_demo -q && break; sleep 1; done
docker exec "$NOME" psql -U postgres -qc "CREATE ROLE pcpr_owner; CREATE ROLE pcpr_app; CREATE ROLE pcpr_leitura;" >/dev/null
docker exec -i "$NOME" pg_restore -U postgres -d restauracao_demo --exit-on-error --no-owner <"$DUMP"
q() { docker exec "$NOME" psql -U postgres -d restauracao_demo -XAtq -v ON_ERROR_STOP=1 -c "$1"; }

# 3. Contagens
RELATORIO="$TRAB/relatorio.txt"
{
  echo "Restauração-teste $INST em $(date -Is) — origem: $ORIGEM — dump: $(basename "$DUMP")"
  for t in identidade_usuario viagens_oficio viagens_documento auditoria_evento django_migrations plataforma_outbox; do
    printf '  %-22s %s\n' "$t" "$(q "SELECT count(*) FROM $t")"
  done
} | tee "$RELATORIO"
[ "$(q 'SELECT count(*) FROM django_migrations')" -gt 0 ] || morrer "banco restaurado sem migrações"

# 4. Cadeia de auditoria com o código do produto (mesma imagem da instância)
docker run --rm --network "$REDE" --read-only --tmpfs /tmp \
  -e DJANGO_SETTINGS_MODULE=config.settings.preview -e APP_ENV=preview -e DEMO_MODE=false \
  -e DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  -e POSTGRES_HOST=db -e POSTGRES_DB=restauracao_demo -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD="$SENHA" "$PCPR_IMAGEM" tarefa verificar_auditoria | tee -a "$RELATORIO"

# 5. Arquivos com SHA-256 do CONTEÚDO gravado no banco: documentos gerados, vias assinadas e
#    anexos de prestação — todos existem e conferem. (coffee_via.sha256 é o da folha HTML.)
for t in viagens_documento viagens_viaassinada viagens_anexoprestacao; do
  q "COPY (SELECT sha256 || '  ' || arquivo FROM $t WHERE arquivo <> '' AND sha256 <> '') TO STDOUT"
done >"$TRAB/documentos.sha256"
TOTAL="$(wc -l <"$TRAB/documentos.sha256")"
if [ "$TOTAL" -gt 0 ]; then
  ( cd "$MIDIA" && sha256sum -c --quiet "$TRAB/documentos.sha256" ) || morrer "arquivos divergentes do banco"
fi
# Demais anexos (coffee, eventos): só existência.
AUSENTES="$(anexos_ausentes "$MIDIA" q)"
[ -z "$AUSENTES" ] || { sed 's/^/  faltando: /' <<<"$AUSENTES"
  morrer "$(wc -l <<<"$AUSENTES") anexo(s) referenciado(s) no banco ausente(s) no backup"; }
echo "  arquivos com SHA-256 conferido: $TOTAL (documentos, vias assinadas, anexos de prestação); demais anexos presentes" | tee -a "$RELATORIO"

cp "$RELATORIO" "$ESTADO/ultima-restauracao.txt"
date -Is >"$ESTADO/restauracao-ok"
registrar "restauração-teste ($ORIGEM) APROVADA: $TOTAL arquivos conferidos"
