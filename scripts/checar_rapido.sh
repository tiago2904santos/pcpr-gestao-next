#!/usr/bin/env bash
# Verificação estática rápida antes de cada checkpoint (sem testes): para no primeiro erro.
# A suíte de testes continua em scripts/verificar.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "▶ ruff";        uv run ruff check .
echo "▶ fronteiras";  uv run lint-imports
echo "▶ mypy";        uv run mypy gestao config
echo "▶ bandit";      uv run bandit -q -r gestao config -x "*/tests/*,*/migrations/*"
echo "▶ migrações";   uv run python manage.py makemigrations --check --dry-run > /dev/null
echo "▶ tipos JS";    npx --no-install tsc -p jsconfig.json
echo "✔ estático verde"
