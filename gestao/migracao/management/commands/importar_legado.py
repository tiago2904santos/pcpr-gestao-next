"""Migração única: Eventos Sociais (EV, a base) + Gerenciador de Viagens (GV, só o que falta).

    python manage.py importar_legado --ev "$LEGADO_EV_URL" --gv "$LEGADO_GV_URL" \
        --midia-ev /restauro/02-eventos-sociais/arquivos/media \
        --midia-gv /restauro/01-gerenciador-viagens/arquivos/media \
        --relatorio /var/backups/migracao/relatorio.json [--etapas cadastros,viagens] [--gravar]

Sem `--gravar`, tudo roda numa transação que é DESFEITA no fim (ensaio): o relatório mostra o
que seria criado. Com `--gravar`, cada etapa é uma transação própria; rodar de novo não
duplica (o mapa de correspondência decide o que já entrou).
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gestao.plataforma import auditoria

from ...contexto import Contexto, Relatorio
from ...etapas import ORDEM
from ...fonte import Fonte


class Ensaio(Exception):
    """Desfaz a transação do ensaio depois de contar tudo."""


class Command(BaseCommand):
    help = "Migra os dados do Eventos Sociais e do Gerenciador de Viagens (uma vez)."

    def add_arguments(self, parser):
        parser.add_argument("--ev", default=os.environ.get("LEGADO_EV_URL", ""))
        parser.add_argument("--gv", default=os.environ.get("LEGADO_GV_URL", ""))
        parser.add_argument("--midia-ev", default="")
        parser.add_argument("--midia-gv", default="")
        parser.add_argument("--etapas", default=",".join(ORDEM))
        parser.add_argument("--relatorio", required=True)
        parser.add_argument("--gravar", action="store_true")

    def handle(self, *args, **o):
        if os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "sim"):
            raise CommandError("DEMO_MODE ligado: dados reais nunca entram no PREVIEW.")
        if not o["ev"]:
            raise CommandError("Informe --ev (ou LEGADO_EV_URL).")
        etapas = [e.strip() for e in o["etapas"].split(",") if e.strip()]
        desconhecidas = [e for e in etapas if e not in ORDEM]
        if desconhecidas:
            raise CommandError(f"Etapas desconhecidas: {desconhecidas}")
        lote = f"legado-{timezone.now():%Y%m%dT%H%M%S}"
        relatorio = Relatorio()
        ev = Fonte("ev", o["ev"])
        gv = Fonte("gv", o["gv"]) if o["gv"] else None
        ctx = Contexto(ev=ev, gv=gv, lote=lote, relatorio=relatorio,
                       midia_ev=Path(o["midia_ev"]) if o["midia_ev"] else None,
                       midia_gv=Path(o["midia_gv"]) if o["midia_gv"] else None)
        try:
            if o["gravar"]:
                for nome in (e for e in ORDEM if e in etapas):
                    with transaction.atomic(), auditoria.contexto(None, None, lote):
                        self._etapa(nome, ctx)
            else:
                try:
                    with transaction.atomic(), auditoria.contexto(None, None, lote):
                        for nome in (e for e in ORDEM if e in etapas):
                            self._etapa(nome, ctx)
                        raise Ensaio
                except Ensaio:
                    pass
        finally:
            ev.fechar()
            if gv:
                gv.fechar()
        destino = Path(o["relatorio"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({
            "lote": lote, "gravado": bool(o["gravar"]), "etapas": etapas,
            "contagens": relatorio.contagens, "conferir": relatorio.conferir,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(f"{'GRAVADO' if o['gravar'] else 'ENSAIO (nada gravado)'}: {lote}")
        for entidade, n in sorted(relatorio.contagens.items()):
            self.stdout.write(f"  {entidade}: {n}")
        self.stdout.write(f"  itens para conferir: {len(relatorio.conferir)} → {destino}")

    def _etapa(self, nome: str, ctx: Contexto) -> None:
        modulo = importlib.import_module(f"gestao.migracao.etapas.{nome}")
        self.stdout.write(f"→ {nome}")
        if ctx.usuario_migracao is None:
            # Autor técnico do que não tem autor, mesmo quando só etapas seguintes rodam.
            from ...etapas.cadastros import garantir_usuario_migracao
            garantir_usuario_migracao(ctx)
        modulo.executar(ctx)
