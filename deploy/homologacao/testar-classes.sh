#!/usr/bin/env bash
# Gera, pelo endereço público e autenticado, cada classe documental implementada (dados
# SINTÉTICOS) e confere o formato do arquivo. Somente leitura (GET). Recusa produção.
#
#   deploy/homologacao/testar-classes.sh <instância>
#
# Grava em $ESTADO/classes/ os PDFs baixados e impressoes.tsv (classe, bytes, páginas,
# SHA-256 do texto extraído) para comparar a renderização da VPS com a local.
. "$(dirname "$0")/../vps/lib.sh"
carregar_instancia "${1:-}"
recusar_dados_reais "use somente na homologação (dados sintéticos)"
[ -f "$CONF/smoke.env" ] || morrer "crie $CONF/smoke.env com o usuário de teste"
export PCPR_IMAGEM="${PCPR_IMAGEM:?}"
# shellcheck disable=SC1091
. "$CONF/smoke.env"
read -r -a EXTRA <<<"${PCPR_SMOKE_CURL_OPTS:-}"
B="https://$PCPR_DOMINIO"
SAIDA="$ESTADO/classes"; rm -rf "$SAIDA"; mkdir -p "$SAIDA"
JAR="$SAIDA/.cookies"
FALHAS=0

curl -sS "${EXTRA[@]}" -c "$JAR" -o /dev/null "$B/conta/entrar/"
TOKEN="$(awk '$6=="pcpr_csrf"{print $7}' "$JAR" | tail -1)"
curl -sS "${EXTRA[@]}" -b "$JAR" -c "$JAR" -o /dev/null -H "Referer: $B/conta/entrar/" \
  --data-urlencode "csrfmiddlewaretoken=$TOKEN" --data-urlencode "username=$PCPR_SMOKE_USUARIO" \
  --data-urlencode "password=$PCPR_SMOKE_SENHA" "$B/conta/entrar/"

baixar() {  # baixar <classe> <magia> <consulta-sql-de-caminhos>
  local classe="$1" magia="$2" caminho arq info
  while IFS= read -r caminho; do
    [ -n "$caminho" ] || continue
    arq="$SAIDA/$classe.pdf"; [ "$magia" = PK ] && arq="$SAIDA/$classe.zip"
    info="$(curl -sS "${EXTRA[@]}" -b "$JAR" -o "$arq" -w '%{http_code} %{time_total}' "$B$caminho")"
    if [ "${info%% *}" = 200 ] && head -c 4 "$arq" | grep -q "$magia"; then
      printf '  ok   %-22s %s (%s bytes, %.1fs)\n' "$classe" "$caminho" "$(wc -c <"$arq")" "${info#* }"
      return 0
    fi
  done < <(sql_valor "$3")
  printf '  FALHA %-22s nenhuma URL respondeu %s\n' "$classe" "$magia"; FALHAS=$((FALHAS + 1))
}

echo "Classes documentais em $B"
baixar oficio-pdf '%PDF' "SELECT '/viagens/documentos/' || id || '/?versao=original' FROM viagens_documento WHERE tipo='oficio' AND situacao='pronto' ORDER BY id DESC LIMIT 3"
baixar justificativa-pdf '%PDF' "SELECT '/viagens/documentos/' || id || '/?versao=original' FROM viagens_documento WHERE tipo='justificativa' AND situacao='pronto' ORDER BY id DESC LIMIT 3"
baixar oficio-minuta '%PDF' "SELECT '/viagens/oficios/' || id || '/minuta.pdf' FROM viagens_oficio WHERE situacao='rascunho' ORDER BY id DESC LIMIT 5"
baixar oficio-docx 'PK' "SELECT '/viagens/oficios/' || id || '/documento/oficio.docx' FROM viagens_oficio WHERE situacao='emitido' ORDER BY id DESC LIMIT 3"
baixar termo-pdf '%PDF' "SELECT '/viagens/termos/' || id || '/todos.pdf' FROM viagens_termoautorizacao ORDER BY id DESC LIMIT 7"
baixar termo-docx-zip 'PK' "SELECT '/viagens/termos/' || id || '/todos.zip' FROM viagens_termoautorizacao ORDER BY id DESC LIMIT 7"
baixar plano-pdf '%PDF' "SELECT '/viagens/planos/' || id || '/documento.pdf' FROM viagens_planotrabalho ORDER BY id DESC LIMIT 4"
baixar ordem-pdf '%PDF' "SELECT '/viagens/ordens/' || id || '/documento.pdf' FROM viagens_ordemservico ORDER BY id DESC LIMIT 5"
baixar diario-pdf '%PDF' "SELECT '/viagens/prestacoes/equipe/' || id || '/diario/pdf/' FROM viagens_prestacaocontas ORDER BY id DESC LIMIT 10"
baixar diario-xlsx 'PK' "SELECT '/viagens/prestacoes/equipe/' || id || '/diario/xlsx/' FROM viagens_prestacaocontas ORDER BY id DESC LIMIT 10"
baixar relatorio-pdf '%PDF' "SELECT '/viagens/prestacoes/equipe/' || prestacao_id || '/relatorio/' || id || '/pdf/' FROM viagens_prestacaoservidor ORDER BY id DESC LIMIT 10"
baixar relatorio-docx 'PK' "SELECT '/viagens/prestacoes/equipe/' || prestacao_id || '/relatorio/' || id || '/docx/' FROM viagens_prestacaoservidor ORDER BY id DESC LIMIT 10"
baixar pauta-pdf '%PDF' "SELECT '/agenda/pauta/'"

# Impressão digital para comparar com a renderização local (mesma imagem ⇒ mesmo resultado).
python3 - "$SAIDA" >"$SAIDA/impressoes.tsv" <<'PY' || true
import hashlib, pathlib, re, sys, zlib
for arq in sorted(pathlib.Path(sys.argv[1]).glob("*.pdf")):
    dados = arq.read_bytes()
    paginas = len(re.findall(rb"/Type\s*/Page[^s]", dados))
    fontes = sorted(set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+_-]+)", dados)))
    print(f"{arq.stem}\t{len(dados)}\t{paginas}\t{b','.join(f.split(b'+')[-1] for f in fontes).decode()}")
PY
column -t "$SAIDA/impressoes.tsv" 2>/dev/null | sed 's/^/       /' || true
rm -f "$JAR"
[ "$FALHAS" = 0 ] && echo "Classes documentais: tudo ok." || { echo "Classes documentais: $FALHAS falha(s)."; exit 1; }
