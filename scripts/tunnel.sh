#!/usr/bin/env bash
# Inicia servidor de desenvolvimento com tunnel público via Microsoft Dev Tunnels
# Uso:
#   scripts/tunnel.sh                    # inicia servidor local + tunnel (solicita login na 1ª vez)
#   scripts/tunnel.sh docker             # inicia via Docker Compose + tunnel
#   scripts/tunnel.sh status             # mostra URL do tunnel atual (sem reiniciar)
#   scripts/tunnel.sh logout             # desconecta da conta devtunnel

set -euo pipefail
cd "$(dirname "$0")/.."

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DEVTUNNEL_ID="pcpr-preview"
DEVTUNNEL_PORT="${PREVIEW_PORTA:-8000}"
MODE="${1:-local}"

# Função para instalar devtunnel se não existir
ensure_devtunnel() {
  if ! command -v devtunnel &> /dev/null; then
    echo -e "${YELLOW}📦 Instalando devtunnel CLI...${NC}"
    if command -v npm &> /dev/null; then
      npm install -g @microsoft/devtunnels-cli
    else
      echo -e "${YELLOW}⚠️  npm não encontrado. Instale devtunnel manualmente:${NC}"
      echo "   npm install -g @microsoft/devtunnels-cli"
      echo "   ou veja: https://github.com/Microsoft/dev-tunnels/wiki/CLI-Quick-Start"
      exit 1
    fi
  fi
}

# Função para fazer login (uma única vez)
ensure_logged_in() {
  if ! devtunnel user show &> /dev/null; then
    echo -e "${BLUE}🔐 Faça login em sua conta Microsoft (primeira vez)...${NC}"
    devtunnel user login
  fi
}

# Função para criar/conectar ao tunnel
setup_tunnel() {
  echo -e "${BLUE}🔗 Configurando tunnel '$DEVTUNNEL_ID' na porta $DEVTUNNEL_PORT...${NC}"

  # Cria o tunnel se não existir
  if ! devtunnel list | grep -q "$DEVTUNNEL_ID"; then
    echo "   Criando tunnel..."
    devtunnel create "$DEVTUNNEL_ID" --allow-anonymous
  fi

  # Conecta ao tunnel
  echo "   Conectando..."
  devtunnel connect "$DEVTUNNEL_ID" -p "$DEVTUNNEL_PORT" --allow-anonymous
}

# Função para mostrar status
show_status() {
  echo -e "${BLUE}📊 Verificando tunnel...${NC}"
  if devtunnel list | grep -q "$DEVTUNNEL_ID"; then
    TUNNEL_URL=$(devtunnel list | grep "$DEVTUNNEL_ID" | awk '{print $NF}' || echo "")
    if [ -n "$TUNNEL_URL" ]; then
      echo -e "${GREEN}✅ Tunnel ativo em: $TUNNEL_URL${NC}"
    else
      echo "   Tunnel existe mas não está conectado. Use: scripts/tunnel.sh $MODE"
    fi
  else
    echo "   Tunnel não encontrado. Use: scripts/tunnel.sh $MODE"
  fi
  exit 0
}

# Processa subcomandos
case "$MODE" in
  status)
    ensure_devtunnel
    show_status
    ;;
  logout)
    ensure_devtunnel
    echo -e "${YELLOW}Desconectando...${NC}"
    devtunnel user logout
    echo -e "${GREEN}✅ Desconectado${NC}"
    exit 0
    ;;
  docker)
    echo -e "${BLUE}🐳 Iniciando servidor via Docker...${NC}"
    docker compose -f compose.preview.yml up --build -d
    sleep 3
    echo -e "${GREEN}✅ Servidor Docker rodando em http://localhost:8000${NC}"
    echo ""
    ensure_devtunnel
    ensure_logged_in
    setup_tunnel
    ;;
  local)
    echo -e "${BLUE}🚀 Iniciando servidor local...${NC}"

    # Verifica PostgreSQL
    if ! psql --version &> /dev/null; then
      echo -e "${YELLOW}⚠️  PostgreSQL não encontrado. Use: scripts/tunnel.sh docker${NC}"
      exit 1
    fi

    export DJANGO_SETTINGS_MODULE=config.settings.preview
    export DEMO_MODE=true
    export POSTGRES_DB="${POSTGRES_DB:-pcpr_preview}"
    export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')}"

    # Garante que o banco existe
    if ! psql -lqt | grep -q "^${POSTGRES_DB}|"; then
      echo "   Criando banco '${POSTGRES_DB}'..."
      createdb "$POSTGRES_DB"
    fi

    echo "   Setup Django..."
    uv run python manage.py check --deploy --fail-level ERROR
    uv run python manage.py migrate --noinput
    uv run python manage.py semear_demo --se-vazio
    uv run python manage.py collectstatic --noinput -v0

    echo -e "${GREEN}✅ Servidor pronto em http://localhost:8000${NC}"
    echo ""

    # Inicia worker de background
    uv run python manage.py processar_outbox &
    WORKER_PID=$!
    trap "kill $WORKER_PID" EXIT

    # Setup tunnel
    ensure_devtunnel
    ensure_logged_in

    echo -e "${BLUE}🌐 Iniciando gunicorn + tunnel...${NC}"

    # Inicia gunicorn em background
    uv run gunicorn config.wsgi --bind "127.0.0.1:${DEVTUNNEL_PORT}" --workers 3 &
    GUNICORN_PID=$!

    # Da alguns segundos pro gunicorn subir
    sleep 2

    # Setup e conecta ao tunnel
    setup_tunnel

    # Aguarda
    wait $GUNICORN_PID
    ;;
  *)
    cat << EOF
${BLUE}Dev Tunnels — servidor com acesso público${NC}

Uso:
  scripts/tunnel.sh [local|docker|status|logout]

Modos:
  local     Servidor Django local + tunnel (padrão)
  docker    Servidor via Docker Compose + tunnel
  status    Mostra URL do tunnel sem reiniciar
  logout    Desconecta da conta Microsoft

Exemplos:
  scripts/tunnel.sh              # localhost + tunnel
  scripts/tunnel.sh docker       # Docker + tunnel
  scripts/tunnel.sh status       # mostra URL

Dicas:
  • Na primeira vez, você será redirecionado para fazer login no Microsoft
  • A URL será something-like-kzw1kqz9-8000.brs.devtunnels.ms
  • Login: deixe usuário/senha em branco e clique em Entrar
EOF
    exit 1
    ;;
esac
