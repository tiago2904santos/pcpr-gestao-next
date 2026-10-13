#!/usr/bin/env bash
# Homologação de documentos e worker com DADOS SINTÉTICOS (recusa produção).
#
#   deploy/homologacao/testar-documentos.sh <instância>
#
# 1. Reabre e reemite um ofício sintético → o worker em execução (LISTEN/NOTIFY) gera a
#    versão nova; a versão anterior e seu arquivo são preservados (SHA-256 conferido).
# 2. Falha induzida: a pasta do ano fica sem escrita → a geração falha, o documento fica
#    "falhou" e a outbox reagenda (backoff); devolvida a escrita, o retry automático conclui.
# 3. Baixa o PDF novo pelo endereço público, autenticado (smoke.env).
. "$(dirname "$0")/../vps/lib.sh"
carregar_instancia "${1:-}"
[ "$INST" != producao ] || morrer "este teste altera dados: proibido em produção"
grep -q '^DJANGO_SETTINGS_MODULE=config.settings.preview' "$CONF/app.env" \
  || morrer "só para homologação com dados sintéticos (config.settings.preview)"
export PCPR_IMAGEM="${PCPR_IMAGEM:?}"
MIDIA="$PCPR_DADOS/midia"
FALHAS=0
ok() { printf '  ok   %s\n' "$*"; }
falha() { printf '  FALHA %s\n' "$*"; FALHAS=$((FALHAS + 1)); }

reemitir() {  # reemitir <sigla-unidade> → imprime o id do ofício reemitido
  dc run --rm -T tarefa shell <<PY 2>/dev/null | tail -1
from django.db import transaction
from gestao.identidade.models import Usuario
from gestao.plataforma.auditoria import contexto
from gestao.viagens import services
from gestao.viagens.models import Oficio
u = Usuario.objects.get(login="demo")
of = Oficio.objects.filter(situacao="emitido", unidade__sigla="$1").order_by("-id").first()
with contexto(usuario_id=u.pk, requisicao_id="homologacao-worker"):
    with transaction.atomic():
        services.reabrir(of, u, "Teste de homologação do worker (dados sintéticos).")
    with transaction.atomic():
        services.emitir(Oficio.objects.get(pk=of.pk), u)
print(of.pk)
PY
}
esperar_pronto() {  # esperar_pronto <oficio> <segundos> → 0 quando a versão mais nova estiver pronta
  for _ in $(seq "$2"); do
    [ "$(sql_valor "SELECT count(*) FROM viagens_documento d WHERE d.oficio_id=$1 AND d.situacao<>'pronto'
         AND d.versao=(SELECT max(versao) FROM viagens_documento WHERE oficio_id=$1 AND tipo=d.tipo)")" = 0 ] && return 0
    sleep 1
  done
  return 1
}
conferir_arquivos() {  # todas as versões do ofício existem e conferem com o SHA-256
  sql_valor "COPY (SELECT sha256 || '  ' || arquivo FROM viagens_documento WHERE oficio_id=$1 AND situacao='pronto') TO STDOUT" \
    >"$ESTADO/.docs.sha256"
  ( cd "$MIDIA" && sha256sum -c --quiet "$ESTADO/.docs.sha256" )
}

echo "Documentos e worker — $INST"
# 1. Reemissão pelo worker em execução
OF="$(reemitir ASCOM)"
[[ "$OF" =~ ^[0-9]+$ ]] || morrer "não foi possível reemitir um ofício sintético"
if esperar_pronto "$OF" 120; then ok "ofício $OF reemitido: worker gerou a versão nova"; else falha "worker não gerou os documentos do ofício $OF em 120 s"; fi
VERSOES="$(sql_valor "SELECT string_agg(tipo || ' v' || versao || ' ' || situacao, ', ' ORDER BY tipo, versao) FROM viagens_documento WHERE oficio_id=$OF")"
echo "       versões: $VERSOES"
[ "$(sql_valor "SELECT count(*) FROM viagens_documento WHERE oficio_id=$OF AND versao>1")" -gt 0 ] \
  && ok "versão 2 criada sem apagar a 1" || falha "nenhuma versão nova"
conferir_arquivos "$OF" && ok "arquivos de TODAS as versões presentes e íntegros (SHA-256)" || falha "arquivo divergente"
TIPOS="$(sql_valor "SELECT string_agg(DISTINCT tipo, ', ') FROM viagens_documento WHERE situacao='pronto'")"
echo "       classes documentais já geradas na instância: $TIPOS"

# 2. Falha induzida e retry automático
ANO="$(date +%Y)"
install -d -o 10001 -g 10001 -m 0750 "$MIDIA/documentos/$ANO"
chmod 0550 "$MIDIA/documentos/$ANO"
OF2="$(reemitir DPI)"
sleep 8
FALHOU="$(sql_valor "SELECT count(*) FROM viagens_documento WHERE oficio_id=$OF2 AND situacao='falhou'")"
ERRO="$(sql_valor "SELECT left(ultimo_erro, 90) FROM plataforma_outbox WHERE topico='viagens.documento.gerar' AND ultimo_erro<>'' ORDER BY id DESC LIMIT 1")"
chmod 0750 "$MIDIA/documentos/$ANO"
[ "$FALHOU" -gt 0 ] && ok "falha de escrita registrada ($FALHOU documento(s) 'falhou': $ERRO)" \
  || falha "a falha induzida não foi registrada"
if esperar_pronto "$OF2" 90; then ok "retry automático da outbox concluiu após devolver a escrita"; else falha "retry não concluiu em 90 s"; fi
conferir_arquivos "$OF2" && ok "arquivos do ofício $OF2 íntegros" || falha "arquivo divergente após retry"
[ "$(sql_valor "SELECT count(*) FROM plataforma_outbox WHERE situacao='falhou'")" = 0 ] \
  && ok "nenhuma mensagem com falha definitiva" || falha "há mensagens com falha definitiva"

# 3. Download autenticado da versão nova pelo endereço público
if [ -f "$CONF/smoke.env" ] && [ "${PCPR_SMOKE_MODO:-publico}" = publico ]; then
  # shellcheck disable=SC1091
  . "$CONF/smoke.env"
  read -r -a EXTRA <<<"${PCPR_SMOKE_CURL_OPTS:-}"
  JAR="$(mktemp)"; PDF="$(mktemp)"; trap 'rm -f "$JAR" "$PDF"' EXIT
  B="https://$PCPR_DOMINIO"
  curl -sS "${EXTRA[@]}" -c "$JAR" -o /dev/null "$B/conta/entrar/"
  TOKEN="$(awk '$6=="pcpr_csrf"{print $7}' "$JAR" | tail -1)"
  curl -sS "${EXTRA[@]}" -b "$JAR" -c "$JAR" -o /dev/null -H "Referer: $B/conta/entrar/" \
    --data-urlencode "csrfmiddlewaretoken=$TOKEN" --data-urlencode "username=$PCPR_SMOKE_USUARIO" \
    --data-urlencode "password=$PCPR_SMOKE_SENHA" "$B/conta/entrar/"
  DOC="$(sql_valor "SELECT id FROM viagens_documento WHERE oficio_id=$OF AND situacao='pronto' ORDER BY versao DESC, id DESC LIMIT 1")"
  SHA="$(sql_valor "SELECT sha256 FROM viagens_documento WHERE id=$DOC")"
  CODIGO="$(curl -sS "${EXTRA[@]}" -b "$JAR" -o "$PDF" -w '%{http_code} %{content_type}' "$B/viagens/documentos/$DOC/?versao=original")"
  if [[ "$CODIGO" == "200 application/pdf"* ]] && [ "$(sha256sum "$PDF" | cut -d' ' -f1)" = "$SHA" ]; then
    ok "PDF $DOC baixado por HTTPS confere com o SHA-256 do banco ($(wc -c <"$PDF") bytes)"
  else
    falha "download HTTPS do documento $DOC → $CODIGO"
  fi
fi

[ "$FALHAS" = 0 ] && echo "Documentos e worker: tudo ok." || { echo "Documentos e worker: $FALHAS falha(s)."; exit 1; }
