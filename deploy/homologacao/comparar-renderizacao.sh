#!/usr/bin/env bash
# Exporta uma amostra de documentos SINTÉTICOS da instância e os renderiza de novo com a
# imagem em execução — prova que a VPS reproduz o PDF gravado. Para comparar com a máquina
# local, leve $ESTADO/renderizacao/amostra.json e vps.json (só dados fictícios) e siga o
# cabeçalho de comparar_renderizacao.py.
#
#   deploy/homologacao/comparar-renderizacao.sh <instância> [quantidade]
. "$(dirname "$0")/../vps/lib.sh"
carregar_instancia "${1:-}"
[ "$INST" != producao ] || morrer "não exporte dados de produção"
export PCPR_IMAGEM="${PCPR_IMAGEM:?}"
N="${2:-6}"
DIR="$ESTADO/renderizacao"; mkdir -p "$DIR"; chmod 0755 "$DIR"
sql_valor "SELECT json_agg(json_build_object('id', id, 'tipo', tipo, 'dados', dados, 'sha256', sha256))
           FROM (SELECT id, tipo, dados, sha256, row_number() OVER (PARTITION BY tipo ORDER BY id DESC) AS n
                 FROM viagens_documento WHERE situacao='pronto') d WHERE n <= $N" >"$DIR/amostra.json"
chmod 0644 "$DIR/amostra.json"
docker run --rm --read-only --tmpfs /tmp --network none -e XDG_CACHE_HOME=/tmp \
  -e DJANGO_SETTINGS_MODULE=config.settings.test --user 10001:10001 \
  -v "$DIR:/comparacao" -v "$DEPLOY_DIR/homologacao/comparar_renderizacao.py:/opt/comparar.py:ro" \
  --entrypoint python "$PCPR_IMAGEM" /opt/comparar.py renderizar /comparacao/amostra.json >"$DIR/vps.json"
echo "Renderização na VPS (mesmos dados, imagem em execução):"
python3 "$DEPLOY_DIR/homologacao/comparar_renderizacao.py" comparar "$DIR/vps.json" "$DIR/vps.json"
echo "Arquivos para comparar com a máquina local: $DIR/amostra.json e $DIR/vps.json"
