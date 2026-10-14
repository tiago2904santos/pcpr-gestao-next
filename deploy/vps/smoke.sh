#!/usr/bin/env bash
# Smoke test de uma instância pelo endereço implantado (ou pela porta local, antes do DNS).
#
#   deploy/vps/smoke.sh <instância>
#
# Modo (instancia.env): PCPR_SMOKE_MODO=publico (padrão: https://$PCPR_DOMINIO) ou local
# (http://127.0.0.1:$PCPR_PORTA com Host/X-Forwarded-Proto, como o proxy envia).
# Opções extras de curl (ex.: --resolve, --cacert): PCPR_SMOKE_CURL_OPTS.
# Login real (opcional): $CONF/smoke.env (0600) com PCPR_SMOKE_USUARIO e PCPR_SMOKE_SENHA.
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
FALHAS=0
ok() { printf '  ok   %s\n' "$*"; }
falha() { printf '  FALHA %s\n' "$*"; FALHAS=$((FALHAS + 1)); }

read -r -a EXTRA <<<"${PCPR_SMOKE_CURL_OPTS:-}"
if [ "${PCPR_SMOKE_MODO:-publico}" = local ]; then
  BASE="http://127.0.0.1:$PCPR_PORTA"
  CABEC=(-H "Host: $PCPR_DOMINIO" -H "X-Forwarded-Proto: https" -H "X-Real-IP: 127.0.0.1")
  HTTPS=0
else
  BASE="https://$PCPR_DOMINIO"
  CABEC=()
  HTTPS=1
fi
JAR="$TMP/cookies"
pedir() {  # pedir <saida-prefixo> <caminho> [args curl…] → status em <prefixo>.status
  local pre="$1" caminho="$2"; shift 2
  curl -sS -m 30 "${EXTRA[@]}" "${CABEC[@]}" -b "$JAR" -c "$JAR" -D "$TMP/$pre.h" \
    -o "$TMP/$pre.corpo" -w '%{http_code}' "$@" "$BASE$caminho" >"$TMP/$pre.status" \
    || echo 000 >"$TMP/$pre.status"
  cat "$TMP/$pre.status"
}
cabecalho() { grep -i "^$2:" "$TMP/$1.h" | head -1 | cut -d: -f2- | tr -d '\r' | sed 's/^ //'; }

echo "Smoke test de $INST em $BASE"

# Saúde
[ "$(pedir saude /saude/)" = 200 ] && grep -q '"ok"' "$TMP/saude.corpo" \
  && ok "/saude/ 200 (banco ok)" || falha "/saude/ → $(cat "$TMP/saude.status")"

# Login e cabeçalhos de segurança
if [ "$(pedir entrar /conta/entrar/)" = 200 ]; then ok "/conta/entrar/ 200"; else falha "/conta/entrar/ → $(cat "$TMP/entrar.status")"; fi
for h in content-security-policy x-frame-options x-content-type-options referrer-policy cross-origin-opener-policy; do
  [ -n "$(cabecalho entrar "$h")" ] && ok "cabeçalho $h" || falha "cabeçalho $h ausente"
done
if [ "$HTTPS" = 1 ]; then
  [ -n "$(cabecalho entrar strict-transport-security)" ] && ok "HSTS" || falha "HSTS ausente"
  grep -i '^set-cookie: pcpr_csrf=' "$TMP/entrar.h" | grep -qi 'secure' \
    && ok "cookie CSRF com Secure" || falha "cookie CSRF sem Secure"
  CODIGO="$(curl -sS -m 15 "${EXTRA[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "http://$PCPR_DOMINIO/" || true)"
  [[ "$CODIGO" =~ ^30[178]\ https:// ]] && ok "http → https ($CODIGO)" || falha "http não redireciona para https ($CODIGO)"
fi
if grep -qiE 'localhost|127\.0\.0\.1|:8000' "$TMP/entrar.corpo"; then
  falha "HTML referencia localhost/127.0.0.1/:8000"
else
  ok "nenhuma referência a localhost no HTML"
fi

# Proteção: sem sessão, páginas redirecionam ao login
pedir raiz / >/dev/null
[[ "$(cat "$TMP/raiz.status")" = 302 && "$(cabecalho raiz location)" == */conta/entrar/* ]] \
  && ok "/ sem sessão → login" || falha "/ sem sessão → $(cat "$TMP/raiz.status")"

# Estáticos com hash e cache longo (WhiteNoise)
CSS="$(grep -oE '/static/[^"]+\.css' "$TMP/entrar.corpo" | head -1 || true)"
if [ -n "$CSS" ] && [ "$(pedir css "$CSS")" = 200 ]; then
  [[ "$(cabecalho css cache-control)" == *max-age=* ]] && ok "estático $CSS (cache: $(cabecalho css cache-control))" \
    || falha "estático sem Cache-Control"
else
  falha "estático da página de login não carregou (${CSS:-nenhum encontrado})"
fi

# Documentos nunca expostos diretamente
for caminho in /media/documentos/ /var/media/ /static/../var/media/; do
  s="$(pedir midia "$caminho")"
  [ "$s" != 200 ] && ok "$caminho não exposto ($s)" || falha "$caminho respondeu 200"
done

# Fluxo autenticado (opcional): login → lista → download de PDF autorizado
if [ -f "$CONF/smoke.env" ]; then
  # shellcheck disable=SC1091
  . "$CONF/smoke.env"
  rm -f "$JAR"; pedir entrar /conta/entrar/ >/dev/null
  TOKEN="$(awk '$6=="pcpr_csrf"{print $7}' "$JAR" | tail -1)"
  s="$(pedir post /conta/entrar/ -H "Referer: https://$PCPR_DOMINIO/conta/entrar/" \
        --data-urlencode "csrfmiddlewaretoken=$TOKEN" \
        --data-urlencode "username=$PCPR_SMOKE_USUARIO" --data-urlencode "password=$PCPR_SMOKE_SENHA")"
  [ "$s" = 302 ] && ok "login com senha ($PCPR_SMOKE_USUARIO)" || falha "login → $s"
  [ "$(pedir lista /viagens/oficios/)" = 200 ] && ok "/viagens/oficios/ 200 autenticado" \
    || falha "/viagens/oficios/ → $(cat "$TMP/lista.status")"
  DOC="$(sql_valor "SELECT id FROM viagens_documento WHERE situacao='pronto' AND arquivo<>'' ORDER BY id DESC LIMIT 1" 2>/dev/null || true)"
  if [ -n "$DOC" ]; then
    s="$(pedir pdf "/viagens/documentos/$DOC/")"
    if [ "$s" = 200 ] && head -c 5 "$TMP/pdf.corpo" | grep -q '%PDF-'; then
      ok "download do documento $DOC (PDF, $(wc -c <"$TMP/pdf.corpo") bytes)"
    else
      falha "download do documento $DOC → $s"
    fi
    rm -f "$JAR"
    s="$(pedir pdfanon "/viagens/documentos/$DOC/")"
    # Só o redirecionamento ao login prova a proteção (404/500 seria rota quebrada).
    [[ "$s" = 302 && "$(cabecalho pdfanon location)" == */conta/entrar/* ]] \
      && ok "documento sem sessão → login" || falha "documento sem sessão → $s (esperado 302 para o login)"
  else
    echo "  (sem documento pronto no banco para testar o download)"
  fi
fi

if [ "$FALHAS" -gt 0 ]; then echo "Smoke test: $FALHAS falha(s)."; exit 1; fi
echo "Smoke test: tudo ok."
