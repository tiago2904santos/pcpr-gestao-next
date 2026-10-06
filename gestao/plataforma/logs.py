"""Filtro de log que tira segredos de URL das mensagens (o token do feed ICS da agenda
aparece no caminho: "Not Found: /agenda/ics/<token>.ics", orçamento SQL excedido…)."""

from __future__ import annotations

import logging
import re

PADRAO = re.compile(r"(/agenda/ics/)[^/\s'\"?]+")


def _mascarar(valor):
    return PADRAO.sub(r"\1[token]", valor) if isinstance(valor, str) else valor


class MascararSegredos(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _mascarar(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_mascarar(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _mascarar(v) for k, v in record.args.items()}
        return True
