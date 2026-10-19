"""Limites de uso das páginas públicas, contados no banco (`ContadorDeLimite`).

O cache padrão é local a cada processo: com três workers do gunicorn (e réplicas), um limite
contado nele valia três vezes ou mais. Aqui a contagem é um upsert atômico do PostgreSQL —
uma janela fixa por chave, reiniciada quando passa do prazo —, igual para todos os processos.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.utils import timezone

# Tabela de `ContadorDeLimite`. Nos dois CASE, `inicio` e `total` são os valores ANTERIORES
# da linha (o PostgreSQL avalia o SET inteiro sobre a linha antiga).
_SQL = """
INSERT INTO automacao_contadordelimite (chave, inicio, total) VALUES (%s, %s, 1)
ON CONFLICT (chave) DO UPDATE SET
    total = CASE WHEN automacao_contadordelimite.inicio <= %s THEN 1
                 ELSE automacao_contadordelimite.total + 1 END,
    inicio = CASE WHEN automacao_contadordelimite.inicio <= %s THEN EXCLUDED.inicio
                  ELSE automacao_contadordelimite.inicio END
RETURNING total
"""


def exceder(chave: str, maximo: int, janela: timedelta) -> bool:
    """Conta mais um uso de `chave` e diz se passou de `maximo` na janela atual."""
    agora = timezone.now()
    vencida = agora - janela
    with connection.cursor() as cursor:
        cursor.execute(_SQL, [chave[:120], agora, vencida, vencida])
        total = cursor.fetchone()[0]
    return total > maximo
