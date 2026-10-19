"""Exporta a trilha de auditoria do Eventos Sociais (EV) dos módulos migrados como ARQUIVO de
consulta, só leitura (G8 da migração de eventos e coffee break):

    python manage.py exportar_auditoria_legado --ev "$LEGADO_EV_URL" \
        --saida /restauro/relatorios/auditoria-legado-eventos.json

A trilha nova (`auditoria_evento`) é escrita só pelo gatilho do banco — nunca por aqui. O
arquivo guarda as linhas de `auditoria_registroauditoria` das solicitações de evento, do coffee
break e dos catálogos de eventos, como estão no legado (com os valores alterados: é o registro
do negócio, por isso fica FORA do Git). Na saída do comando, só contagens.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...fonte import Fonte

PREFIXOS = ("solicitacoes.", "coffee_break.")
CATALOGOS = ("cadastros.servico", "cadastros.tipoevento", "cadastros.tipoeventoequipe",
             "cadastros.equipe", "cadastros.orgaoresponsavel", "cadastros.unidademovel",
             "cadastros.textodespacho", "cadastros.regiao")


def relevante(modelo: str) -> bool:
    return modelo.startswith(PREFIXOS) or modelo in CATALOGOS


def _json(v: Any) -> Any:
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    raise TypeError(type(v).__name__)


class Command(BaseCommand):
    help = "Exporta a auditoria do legado (eventos e coffee break) para um arquivo JSON."

    def add_arguments(self, parser):
        parser.add_argument("--ev", default=os.environ.get("LEGADO_EV_URL", ""))
        parser.add_argument("--saida", required=True)

    def handle(self, *args, **o):
        if not o["ev"]:
            raise CommandError("Informe --ev (ou LEGADO_EV_URL).")
        ev = Fonte("ev", o["ev"])
        try:
            linhas = [r for r in ev.tabela("auditoria_registroauditoria")
                      if relevante(r.get("modelo") or "")]
        finally:
            ev.fechar()
        por_modelo = Counter(r["modelo"] for r in linhas)
        destino = Path(o["saida"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({
            "gerado_em": timezone.now().isoformat(),
            "origem": "eventos_sociais.auditoria_registroauditoria",
            "filtro": {"prefixos": PREFIXOS, "catalogos": CATALOGOS},
            "somente_leitura": True,
            "contagens": dict(sorted(por_modelo.items())),
            "linhas": linhas,
        }, ensure_ascii=False, indent=1, default=_json), encoding="utf-8")
        self.stdout.write(f"{len(linhas)} linhas exportadas → {destino}")
        for modelo, n in sorted(por_modelo.items()):
            self.stdout.write(f"  {modelo}: {n}")
