#!/usr/bin/env bash
# Gera, pelo endereço público e autenticado, cada classe documental implementada (dados
# SINTÉTICOS) e confere o formato do arquivo. Somente leitura (GET). Recusa produção.
#
#   deploy/homologacao/testar-classes.sh <instância>
#
# Grava em $ESTADO/classes/ os PDFs baixados e impressoes.tsv (classe, bytes, SHA-256 do
# arquivo, páginas, fontes embutidas e SHA-256 do texto extraído) para comparar a
# renderização da VPS com a local.
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
# O texto vem do pypdf da própria imagem (o host pode não ter pypdf).
docker run --rm -i --read-only --network none --user "$(id -u):$(id -g)" -v "$SAIDA:/classes:ro" \
  --entrypoint python "${PCPR_IMAGEM:?}" - >"$SAIDA/impressoes.tsv" <<'PY'
import hashlib, pathlib
from pypdf import PdfReader
print("arquivo\tbytes\tsha256\tpaginas\tfontes\tsha256_texto")
for arq in sorted(pathlib.Path("/classes").glob("*.pdf")):
    dados = arq.read_bytes()
    leitor = PdfReader(arq)
    fontes = set()
    for pagina in leitor.pages:
        for fonte in ((pagina.get("/Resources") or {}).get("/Font") or {}).values():
            fontes.add(str(fonte.get_object().get("/BaseFont", "")).split("+")[-1])
    texto = "\f".join(p.extract_text() or "" for p in leitor.pages)
    print(f"{arq.stem}\t{len(dados)}\t{hashlib.sha256(dados).hexdigest()[:16]}\t{len(leitor.pages)}"
          f"\t{','.join(sorted(fontes))}\t{hashlib.sha256(texto.encode()).hexdigest()[:16]}")
PY
{ column -t "$SAIDA/impressoes.tsv" 2>/dev/null || cat "$SAIDA/impressoes.tsv"; } | sed 's/^/       /'
rm -f "$JAR"
[ "$FALHAS" = 0 ] && echo "Classes documentais: tudo ok." || { echo "Classes documentais: $FALHAS falha(s)."; exit 1; }
