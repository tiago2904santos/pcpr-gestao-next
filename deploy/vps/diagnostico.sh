#!/usr/bin/env bash
# Diagnóstico SOMENTE LEITURA da VPS (missão de implantação — deploy/README.md §1).
#
# Não instala, não altera, não reinicia nada. Não imprime segredos: variáveis de ambiente de
# contêineres e arquivos .env NÃO são lidos. Rode como root (ou com sudo) para ver tudo:
#
#   curl -fsSL <url-raw-deste-arquivo> -o diagnostico.sh   # ou copie o arquivo
#   sudo bash diagnostico.sh | tee diagnostico-$(hostname)-$(date +%F).txt
#
# Envie o .txt gerado de volta (revise antes: ele lista domínios, portas e serviços).
set -u
export LC_ALL=C

secao() { printf '\n===== %s =====\n' "$1"; }
tem() { command -v "$1" >/dev/null 2>&1; }
rodar() { printf '$ %s\n' "$*"; timeout 20 "$@" 2>&1 | head -n "${LIMITE:-80}"; }

secao "IDENTIFICAÇÃO"
date -Is
rodar hostnamectl
rodar cat /etc/os-release
rodar uname -a
printf 'usuário: %s (uid=%s) grupos: %s\n' "$(id -un)" "$(id -u)" "$(id -Gn)"
rodar uptime

secao "CAPACIDADE"
rodar nproc
rodar lscpu
rodar free -h
rodar swapon --show
rodar df -hT -x tmpfs -x devtmpfs -x overlay
rodar lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
LIMITE=25 rodar ps -eo pid,user,%cpu,%mem,rss,comm --sort=-%mem
rodar vmstat 1 3
tem systemd-detect-virt && rodar systemd-detect-virt

secao "SERVIÇOS ATIVOS"
LIMITE=150 rodar systemctl list-units --type=service --state=running --no-pager --no-legend
rodar systemctl list-timers --all --no-pager
rodar systemctl --failed --no-pager

secao "PORTAS EM ESCUTA"
if tem ss; then LIMITE=150 rodar ss -tulpnH; else LIMITE=150 rodar netstat -tulpn; fi

secao "FIREWALL"
tem ufw && rodar ufw status verbose
tem firewall-cmd && rodar firewall-cmd --list-all
tem nft && LIMITE=200 rodar nft list ruleset
tem iptables && LIMITE=120 rodar iptables -S
tem fail2ban-client && rodar fail2ban-client status
tem cscli && rodar cscli decisions list

secao "SSH (somente leitura da configuração efetiva)"
if tem sshd; then
  sshd -T 2>/dev/null | grep -Ei '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|allowusers|allowgroups|maxauthtries) ' || true
fi
for d in /root /home/*; do
  [ -f "$d/.ssh/authorized_keys" ] && printf '%s: %s chave(s) autorizada(s)\n' "$d" \
    "$(grep -cE '^(ssh-|ecdsa-|sk-)' "$d/.ssh/authorized_keys")"
done
rodar getent group sudo
rodar getent group docker

secao "DOCKER"
if tem docker; then
  rodar docker version --format '{{.Server.Version}} (API {{.Server.APIVersion}})'
  rodar docker compose version
  rodar docker info --format 'Storage={{.Driver}} Root={{.DockerRootDir}} Containers={{.Containers}} Running={{.ContainersRunning}} Cgroup={{.CgroupVersion}}'
  LIMITE=100 rodar docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
  rodar docker volume ls
  rodar docker network ls
  rodar docker system df
  rodar docker compose ls -a
  [ -f /etc/docker/daemon.json ] && rodar cat /etc/docker/daemon.json
else
  echo "docker: não instalado"
fi
tem podman && rodar podman ps -a

secao "PROXY / SERVIDOR WEB"
for s in nginx apache2 httpd caddy traefik haproxy openlitespeed lsws; do
  systemctl is-active --quiet "$s" 2>/dev/null && echo "ATIVO: $s"
done
if tem nginx; then
  rodar nginx -v
  rodar ls -l /etc/nginx/sites-enabled /etc/nginx/conf.d
  # Nomes de servidor e portas — sem despejar a configuração inteira.
  LIMITE=200 rodar sh -c "nginx -T 2>/dev/null | grep -E '^\s*(server_name|listen|ssl_certificate |proxy_pass|root)\b' | sort | uniq -c"
fi
tem apache2ctl && rodar apache2ctl -S
tem caddy && rodar caddy version
[ -d /usr/local/lsws ] && echo "OpenLiteSpeed/LiteSpeed detectado em /usr/local/lsws"
# Painéis comuns em VPS da Hostinger (templates).
for p in /usr/local/CyberCP /usr/local/cpanel /usr/local/psa /opt/coolify /data/coolify \
         /opt/easypanel /etc/easypanel /usr/local/hestia /opt/dokploy; do
  [ -e "$p" ] && echo "Painel/plataforma detectado: $p"
done

secao "TLS / CERTIFICADOS"
tem certbot && rodar certbot certificates
[ -d /etc/letsencrypt/live ] && rodar ls -l /etc/letsencrypt/live
tem acme.sh && echo "acme.sh presente"

secao "BANCOS DE DADOS"
for s in postgresql mysql mariadb mongod redis-server redis; do
  systemctl is-active --quiet "$s" 2>/dev/null && echo "ATIVO (host): $s"
done
tem psql && rodar psql --version
tem pg_lsclusters && rodar pg_lsclusters
tem mysql && rodar mysql --version

secao "AGENDAMENTOS E BACKUPS"
rodar ls -l /etc/cron.d /etc/cron.daily
rodar crontab -l
for u in $(cut -d: -f1 /etc/passwd); do
  crontab -l -u "$u" >/dev/null 2>&1 && echo "crontab do usuário: $u"
done
for t in restic borg rclone duplicity rsnapshot; do tem "$t" && echo "ferramenta de backup: $t"; done

secao "ATUALIZAÇÕES DE SEGURANÇA"
if tem apt-get; then
  rodar sh -c "apt list --upgradable 2>/dev/null | grep -c security || true"
  rodar sh -c "apt list --upgradable 2>/dev/null | wc -l"
  rodar sh -c "dpkg -l unattended-upgrades 2>/dev/null | tail -1"
  [ -f /etc/apt/apt.conf.d/20auto-upgrades ] && rodar cat /etc/apt/apt.conf.d/20auto-upgrades
  [ -f /var/run/reboot-required ] && echo "REINÍCIO PENDENTE: $(cat /var/run/reboot-required)"
fi
tem dnf && rodar dnf -q check-update --security

secao "REDE E DNS"
rodar ip -brief addr
rodar ip route
rodar cat /etc/resolv.conf
rodar hostname -f
# IP público (para a proposta de registro DNS) — consulta HTTPS simples, sem dados enviados.
tem curl && rodar curl -s4 --max-time 5 https://api.ipify.org

secao "AGENTES DO PROVEDOR / MONITORAMENTO"
for s in hostinger qemu-guest-agent monarx-agent netdata node_exporter prometheus grafana-server \
         zabbix-agent zabbix-agent2 datadog-agent; do
  systemctl is-active --quiet "$s" 2>/dev/null && echo "ATIVO: $s"
done

secao "PASTAS QUE A IMPLANTAÇÃO USARIA (não podem conflitar)"
for d in /srv/pcpr /etc/pcpr /opt/pcpr; do
  [ -e "$d" ] && echo "JÁ EXISTE: $d" || echo "livre: $d"
done

echo
echo "Fim do diagnóstico (nada foi alterado)."
