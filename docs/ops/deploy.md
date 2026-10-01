# Deploy

Processos (systemd ou contêiner):
| Serviço | Comando |
|---|---|
| `pcpr-web` | `gunicorn config.wsgi -w 4 --bind 127.0.0.1:8000` |
| `pcpr-outbox` | `python manage.py processar_outbox` |
| cron diário | `python manage.py verificar_auditoria` |

Passos: `uv sync --frozen --no-dev` → `manage.py migrate` → `manage.py collectstatic` →
`manage.py check --deploy` → reiniciar serviços. Variáveis em `.env.example` (valores no
gerenciador de segredos, nunca no Git). Nginx na frente com TLS, `X-Real-IP` e
`X-Forwarded-Proto`. HSTS preload fica a cargo da infraestrutura do domínio institucional.

Dependências do sistema: `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`
(WeasyPrint/PDF/A).
