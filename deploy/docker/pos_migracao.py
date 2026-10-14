"""Privilégios aplicados depois de cada `migrate` (docs/ops/banco.md).

Roda com o papel dono do schema (`pcpr_owner`). Idempotente. Os privilégios padrão
(ALTER DEFAULT PRIVILEGES, em deploy/postgres/01-papeis.sh) cobrem as tabelas novas; aqui
garantimos as existentes e retiramos da aplicação o direito de alterar a auditoria.
"""

from __future__ import annotations

import os
import sys

import django

sys.path.insert(0, os.environ.get("PCPR_APP_DIR", "/app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

from django.db import connection  # noqa: E402

APP = os.environ.get("PCPR_PAPEL_APP", "pcpr_app")
LEITURA = os.environ.get("PCPR_PAPEL_LEITURA", "pcpr_leitura")

with connection.cursor() as cur:
    cur.execute("SELECT current_user, current_database()")
    usuario, banco = cur.fetchone()
    cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN (%s, %s)", [APP, LEITURA])
    papeis = {linha[0] for linha in cur.fetchall()}
    if APP not in papeis:
        # Banco sem separação de papéis (ex.: instância antiga): nada a ajustar.
        sys.stdout.write(f"pós-migração: papel {APP} inexistente em {banco}; nada a fazer.\n")
        raise SystemExit(0)
    cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{APP}"')
    cur.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{APP}"')
    # Trilha de auditoria: a aplicação só insere e lê (o trigger bloqueia o resto também).
    cur.execute("SELECT to_regclass('public.auditoria_evento') IS NOT NULL")
    if cur.fetchone()[0]:
        cur.execute(f'REVOKE UPDATE, DELETE, TRUNCATE ON auditoria_evento FROM "{APP}"')
    if LEITURA in papeis:
        cur.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{LEITURA}"')
    sys.stdout.write(f"pós-migração: privilégios de {APP} aplicados em {banco} "
                     f"(executado por {usuario}).\n")
