"""Diagnóstico do ambiente: `manage.py doctor`.

Verifica o que costuma quebrar: versão do Python, banco e migrações, triggers de
auditoria, worker da outbox, WeasyPrint/fontes do PDF, artefatos de front-end
vendorizados, configuração do ambiente. Sai com código 1 se algo estiver errado.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from gestao.plataforma import ambiente
from gestao.plataforma.models import MensagemOutbox


class Command(BaseCommand):
    help = "Diagnostica o ambiente e aponta como corrigir cada problema."

    def handle(self, *args, **opts):
        self.falhas = 0
        self.item("Python ≥ 3.13", sys.version_info >= (3, 13), sys.version.split()[0])
        self.item("Ambiente (APP_ENV)", ambiente.atual() in ambiente.AMBIENTES,
                  ambiente.atual().upper())
        try:
            connection.ensure_connection()
            with connection.cursor() as cur:
                cur.execute("SHOW server_version")
                versao = cur.fetchone()[0]
            self.item("PostgreSQL acessível", True, versao)
        except Exception as exc:
            self.item("PostgreSQL acessível", False, f"{exc} → confira POSTGRES_* no .env")
            return self.fim()
        executor = MigrationExecutor(connection)
        pendentes = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.item("Migrações aplicadas", not pendentes,
                  f"{len(pendentes)} pendente(s) → manage.py migrate" if pendentes else "ok")
        with connection.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'auditoria_%%' "
                "AND tgrelid <> 'auditoria_evento'::regclass"
            )
            gatilhos = cur.fetchone()[0]
        self.item("Triggers de auditoria", gatilhos > 0, f"{gatilhos} tabela(s) auditada(s)")
        atrasadas = MensagemOutbox.objects.filter(
            situacao=MensagemOutbox.Situacao.PENDENTE,
            disponivel_em__lt=timezone.now() - timedelta(minutes=5),
        ).count()
        falhas = MensagemOutbox.objects.filter(situacao=MensagemOutbox.Situacao.FALHOU).count()
        self.item("Outbox em dia", atrasadas == 0,
                  f"{atrasadas} atrasada(s) → rode manage.py processar_outbox" if atrasadas
                  else "ok", aviso=True)
        self.item("Outbox sem falhas definitivas", falhas == 0, f"{falhas} falha(s)", aviso=True)
        try:
            import weasyprint

            self.item("WeasyPrint", True, weasyprint.__version__)
        except Exception as exc:  # pragma: no cover - depende do SO
            self.item("WeasyPrint", False, f"{exc} → instale libpango (ver README)")
        base = Path(settings.BASE_DIR)
        for rel in ("static/vendor/htmx.min.js", "static/icons/sprite.svg",
                    "static/fonts/inter-latin-wght-normal.woff2",
                    "gestao/viagens/documentos_assets/fontes/LiberationSerif-Regular.ttf"):
            self.item(f"Arquivo {rel}", (base / rel).is_file(),
                      "ok" if (base / rel).is_file() else "→ npm ci && npm run vendor")
        if ambiente.eh_producao():
            self.item("DEBUG desligado", not settings.DEBUG, str(settings.DEBUG))
        return self.fim()

    def item(self, nome: str, ok: bool, detalhe: str = "", *, aviso: bool = False) -> None:
        if ok:
            simbolo = self.style.SUCCESS("✔")
        elif aviso:
            simbolo = self.style.WARNING("!")
        else:
            simbolo = self.style.ERROR("✘")
            self.falhas += 1
        self.stdout.write(f" {simbolo} {nome}: {detalhe}")

    def fim(self):
        if self.falhas:
            self.stderr.write(self.style.ERROR(f"{self.falhas} problema(s) encontrado(s)."))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("Ambiente saudável."))
