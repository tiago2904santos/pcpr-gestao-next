# Deploy

Processos (systemd ou contêiner):
| Serviço | Comando |
|---|---|
| `pcpr-web` | `gunicorn config.wsgi -w 4 --bind 127.0.0.1:8000` |
| `pcpr-outbox` | `python manage.py processar_outbox` |
| `pcpr-importador` | `python manage.py processar_importacoes --concorrencia 2` |
| cron diário | `python manage.py verificar_auditoria` |

Passos: `uv sync --frozen --no-dev` → `manage.py migrate` → `manage.py collectstatic` →
`manage.py check --deploy` → reiniciar serviços. Variáveis em `.env.example` (valores no
gerenciador de segredos, nunca no Git). Nginx na frente com TLS, `X-Real-IP` e
`X-Forwarded-Proto`. HSTS preload fica a cargo da infraestrutura do domínio institucional.
O Nginx limita o corpo a 32 MiB (`client_max_body_size 32m;`) e
não serve `MEDIA_ROOT`: os arquivos (PDFs emitidos, vias assinadas) só saem pelas views, com
autorização por objeto. A aplicação recusa com 413 acima de 16 MiB nas rotas comuns
(via assinada até 15 MiB), e acima de 26 MiB na entrada de importação (arquivo até
25 MiB mais formulário). O lote envia um arquivo por requisição.

Contêiner: o `Dockerfile` da raiz é a imagem de produção (gunicorn + WhiteNoise; entrypoint
`scripts/preview-entrypoint.sh web|worker`). O PREVIEW (`compose.preview.yml`) usa a mesma
imagem — ver `docs/ops/preview.md`. Em produção, `DEMO_MODE` não pode existir (os settings
recusam).

Dependências do sistema: `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`
(WeasyPrint/PDF/A).
Importação documental: LibreOffice Writer/Calc/Impress, Poppler e Tesseract com
português/inglês (já incluídos no Dockerfile). Operação e limites em
`docs/ops/importacao-documental.md`.

Implantação em VPS com Docker Compose (homologação e produção, imagem por commit aprovado,
backup externo e restauração testada): `deploy/README.md`, ADR 0035 e as evidências em
`docs/ops/implantacao-vps-evidencias.md`.
