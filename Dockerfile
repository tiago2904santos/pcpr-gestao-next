# syntax=docker/dockerfile:1
# Imagem de produção do sistema (usada também pelo PREVIEW — docs/ops/preview.md).
# Mesmo código, settings por variável de ambiente, gunicorn + WhiteNoise (manifest).
#
# Rede com proxy que intercepta TLS (comum em redes institucionais): passe a CA como
# secret, que não fica na imagem —
#   docker build --secret id=ca,src=/caminho/ca.crt -t pcpr-gestao:preview .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# WeasyPrint (PDF/A): Pango e HarfBuzz; fontes do documento vêm embutidas no repositório.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 \
       libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.8.17 \
    && useradd --create-home --uid 1000 pcpr

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export SSL_CERT_FILE=/run/secrets/ca UV_NATIVE_TLS=1; fi \
    && uv sync --frozen --no-dev --no-install-project
COPY --chown=pcpr:pcpr . .

# Estáticos com hash (CompressedManifestStaticFilesStorage). A chave existe só neste passo.
RUN DJANGO_SETTINGS_MODULE=config.settings.preview \
    DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" \
    python manage.py collectstatic --noinput -v0 \
    && mkdir -p var/media && chown -R pcpr:pcpr var

USER pcpr
EXPOSE 8000
ENTRYPOINT ["scripts/preview-entrypoint.sh"]
CMD ["web"]
