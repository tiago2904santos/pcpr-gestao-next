#!/usr/bin/env bash
# Verificação rápida antes de commitar: o mesmo que o CI roda, exceto o navegador.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "▶ ruff";            uv run ruff check .
echo "▶ fronteiras";      uv run lint-imports
echo "▶ mypy";            uv run mypy gestao config
echo "▶ bandit";          uv run bandit -q -r gestao config -x "*/tests/*,*/migrations/*"
echo "▶ migrações";       uv run python manage.py makemigrations --check --dry-run > /dev/null
echo "▶ tipos JS";        npx --no-install tsc -p jsconfig.json
echo "▶ testes";          uv run pytest -m "not e2e and not visual and not a11y and not perf" -n auto -q
echo "✔ tudo verde"
