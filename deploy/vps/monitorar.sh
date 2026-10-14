#!/usr/bin/env bash
# Verificações leves (timer a cada 5 min; sem agente nem stack de monitoramento).
# Alerta só quando o conjunto de problemas MUDA (sem repetir o mesmo alerta a cada execução).
#
#   deploy/vps/monitorar.sh <instância> [--mostrar]
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"
MOSTRAR=0; [ "${2:-}" = --mostrar ] && MOSTRAR=1
export PCPR_IMAGEM="${PCPR_IMAGEM:-indefinida}"
PROBLEMAS=()
p() { PROBLEMAS+=("$*"); }
idade_h() { [ -f "$1" ] && echo $(( ($(date +%s) - $(date -d "$(cat "$1")" +%s)) / 3600 )) || echo 99999; }

# Contêineres
for s in db web worker; do
  id="$(dc ps -q "$s" 2>/dev/null || true)"
  if [ -z "$id" ]; then p "serviço $s não está rodando"; continue; fi
  estado="$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}|{{.RestartCount}}' "$id")"
  IFS='|' read -r st saude reinicios <<<"$estado"
  [ "$st" = running ] || p "serviço $s: $st"
  [ "$saude" = - ] || [ "$saude" = healthy ] || p "serviço $s: saúde $saude"
  # Alerta quando o contador SOBE desde a última verificação (queda/loop), não pelo acumulado.
  antes="$(cat "$ESTADO/reinicios.$s" 2>/dev/null || echo "${reinicios:-0}")"
  echo "${reinicios:-0}" >"$ESTADO/reinicios.$s"
  [ "${reinicios:-0}" -le "$antes" ] || p "serviço $s reiniciou $(( reinicios - antes )) vez(es) nos últimos minutos"
done

# Aplicação pelo endereço público (proxy + TLS)
if [ "${PCPR_SMOKE_MODO:-publico}" = publico ]; then
  read -r -a EXTRA <<<"${PCPR_SMOKE_CURL_OPTS:-}"
  codigo="$(curl -sS -m 10 "${EXTRA[@]}" -o /dev/null -w '%{http_code}' "https://$PCPR_DOMINIO/saude/" || echo 000)"
  [ "$codigo" = 200 ] || p "https://$PCPR_DOMINIO/saude/ → $codigo"
  # Validade do certificado sempre, salvo desligamento explícito (só a simulação com TLS interno
  # do Caddy, de certificados de horas, usa PCPR_MONITOR_CERTIFICADO=nao).
  if [ "${PCPR_MONITOR_CERTIFICADO:-sim}" != nao ]; then
    fim="$(echo | timeout 10 openssl s_client -servername "$PCPR_DOMINIO" -connect "$PCPR_DOMINIO:443" 2>/dev/null \
           | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
    if [ -n "$fim" ]; then
      dias=$(( ($(date -d "$fim" +%s) - $(date +%s)) / 86400 ))
      [ "$dias" -ge 14 ] || p "certificado TLS expira em $dias dia(s)"
    else
      p "não foi possível ler o certificado TLS"
    fi
  fi
fi

# Recursos do host
for alvo in / "$PCPR_DADOS"; do
  uso="$(df -P "$alvo" | awk 'NR==2{gsub("%","",$5); print $5}')"
  [ "$uso" -lt "${PCPR_LIMITE_DISCO:-85}" ] || p "disco $alvo em ${uso}%"
done
mem="$(awk '/MemAvailable/{a=$2} /MemTotal/{t=$2} END{print int(a*100/t)}' /proc/meminfo)"
[ "$mem" -ge 8 ] || p "memória disponível em ${mem}%"
carga="$(awk '{print int($2)}' /proc/loadavg)"; cpus="$(nproc)"
[ "$carga" -le $((cpus * 2)) ] || p "carga média de 5 min = $carga (vCPUs: $cpus)"
midia="$(du -sm "$PCPR_DADOS/midia" 2>/dev/null | cut -f1)"

# Fila de documentos (outbox): falhas definitivas e mensagens paradas (worker travado)
if dc ps -q db >/dev/null 2>&1; then
  falhas="$(sql_valor "SELECT count(*) FROM plataforma_outbox WHERE situacao='falhou'" 2>/dev/null || echo '?')"
  paradas="$(sql_valor "SELECT count(*) FROM plataforma_outbox WHERE situacao='pendente' AND disponivel_em < now() - interval '15 minutes'" 2>/dev/null || echo '?')"
  erros_doc="$(sql_valor "SELECT count(*) FROM viagens_documento WHERE situacao='falhou'" 2>/dev/null || echo 0)"
  [ "$falhas" = 0 ] || p "outbox: $falhas mensagem(ns) com falha definitiva"
  [ "$paradas" = 0 ] || p "outbox: $paradas mensagem(ns) pendente(s) há mais de 15 min (worker parado?)"
  [ "$erros_doc" = 0 ] || p "documentos com erro de geração: $erros_doc"
fi

# Backups, restauração e auditoria
[ "$(idade_h "$ESTADO/backup-ok")" -le 26 ] || p "último backup há mais de 26 h"
if [ -f "$CONF/backup.env" ]; then
  [ "$(idade_h "$ESTADO/backup-externo-ok")" -le 26 ] || p "última cópia EXTERNA há mais de 26 h"
else
  p "backup externo não configurado"
fi
[ "$(idade_h "$ESTADO/restauracao-ok")" -le $((35 * 24)) ] || p "nenhum teste de restauração aprovado nos últimos 35 dias"
[ "$(idade_h "$ESTADO/auditoria-ok")" -le 26 ] || p "verificação da cadeia de auditoria não aprovada nas últimas 26 h"

RESUMO="$(printf '%s\n' "${PROBLEMAS[@]+"${PROBLEMAS[@]}"}" | sort)"
if [ "$MOSTRAR" = 1 ]; then
  echo "Instância $INST — versão $(cat "$ESTADO/versao-ativa" 2>/dev/null || echo '?') — documentos ${midia:-?} MB"
  if [ -z "$RESUMO" ]; then echo "Sem problemas."; else echo "$RESUMO"; fi
fi
ANTERIOR="$(cat "$ESTADO/monitor.ultimo" 2>/dev/null || true)"
if [ "$RESUMO" != "$ANTERIOR" ]; then
  if [ -n "$RESUMO" ]; then alertar PROBLEMA "$(echo "$RESUMO" | paste -sd ';' -)"
  else alertar RESOLVIDO "todos os itens monitorados voltaram ao normal"; fi
  # Só dá o estado por avisado se o webhook entregou; senão, a próxima rodada tenta de novo.
  [ "$ALERTA_ENTREGUE" = 0 ] || printf '%s' "$RESUMO" >"$ESTADO/monitor.ultimo"
fi
# 3 = "há problemas (já alertados)"; qualquer outro código ≠ 0 é falha do próprio monitor.
[ -z "$RESUMO" ] || exit 3
