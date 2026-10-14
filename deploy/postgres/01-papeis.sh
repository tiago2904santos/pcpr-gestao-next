#!/bin/sh
# Executado UMA vez pela imagem oficial do PostgreSQL, na criação do cluster
# (/docker-entrypoint-initdb.d). Cria os papéis de docs/ops/banco.md:
#   pcpr_owner   → dono do banco e do schema; usado só nas migrações (deploy)
#   pcpr_app     → aplicação e worker: SELECT/INSERT/UPDATE/DELETE (auditoria: só INSERT/SELECT)
#   pcpr_leitura → somente SELECT (relatórios/ferramentas); sem login até ser necessário
# O superusuário do cluster (POSTGRES_USER) fica restrito à administração/backup.
set -eu
for variavel in PCPR_OWNER_PASSWORD PCPR_APP_PASSWORD; do
  printenv "$variavel" >/dev/null || { echo "defina $variavel (banco.env)" >&2; exit 1; }
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v banco="$POSTGRES_DB" -v owner_senha="$PCPR_OWNER_PASSWORD" \
  -v app_senha="$PCPR_APP_PASSWORD" <<'SQL'
CREATE ROLE pcpr_owner LOGIN PASSWORD :'owner_senha';
CREATE ROLE pcpr_app LOGIN PASSWORD :'app_senha' CONNECTION LIMIT 60;
CREATE ROLE pcpr_leitura NOLOGIN;

ALTER DATABASE :"banco" OWNER TO pcpr_owner;
REVOKE ALL ON DATABASE :"banco" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"banco" TO pcpr_app;
GRANT CONNECT ON DATABASE :"banco" TO pcpr_leitura;

ALTER SCHEMA public OWNER TO pcpr_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO pcpr_app, pcpr_leitura;

-- Tudo que as migrações (pcpr_owner) criarem nasce com os direitos certos.
ALTER DEFAULT PRIVILEGES FOR ROLE pcpr_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pcpr_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pcpr_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO pcpr_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pcpr_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO pcpr_leitura;

-- Tempo máximo de espera por lock e de transação ociosa (evita conexões presas).
ALTER ROLE pcpr_app SET idle_in_transaction_session_timeout = '5min';
ALTER ROLE pcpr_app SET lock_timeout = '30s';
SQL
echo "Papéis pcpr_owner / pcpr_app / pcpr_leitura criados em $POSTGRES_DB."
