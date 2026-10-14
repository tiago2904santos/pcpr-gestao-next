#!/usr/bin/env bash
# Instala e liga os timers systemd de uma instância (backup, rotinas, monitor, restauração).
#
#   sudo deploy/vps/instalar-timers.sh <instância> [--sem-restauracao]
#
# As unidades chamam /srv/pcpr/infra/deploy/vps/*.sh. Veja o estado com
#   systemctl list-timers 'pcpr-*'   e   journalctl -u 'pcpr-*@<instância>' -n 50
. "$(dirname "$0")/lib.sh"
carregar_instancia "${1:-}"
[ "$(id -u)" = 0 ] || morrer "rode como root"
[ "$DEPLOY_DIR" = /srv/pcpr/infra/deploy ] || \
  morrer "as unidades apontam para /srv/pcpr/infra; clone o repositório lá (deploy/README.md §2)"
install -m 0644 "$DEPLOY_DIR"/systemd/pcpr-*@.service "$DEPLOY_DIR"/systemd/pcpr-*@.timer /etc/systemd/system/
systemctl daemon-reload
TIMERS=(backup rotinas monitor)
[ "${2:-}" = --sem-restauracao ] || TIMERS+=(restauracao-teste)
for t in "${TIMERS[@]}"; do
  systemctl enable --now "pcpr-$t@$INST.timer"
done
systemctl list-timers "pcpr-*@$INST.timer" --no-pager
