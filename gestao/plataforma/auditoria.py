"""API Python da trilha de auditoria mantida pelo banco.

- `contexto(...)` informa ao PostgreSQL quem está agindo (lido pelo trigger);
- `auditar_tabela(...)` gera o SQL que liga o trigger a uma tabela (usado em
  migrações via `migrations.RunSQL`);
- `verificar_cadeia()` recalcula a cadeia de hashes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection
from django.db.migrations.operations import RunSQL


def definir_contexto(usuario_id: int | None, ip: str | None, requisicao_id: str | None) -> None:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.usuario_id', %s, false), "
            "set_config('app.ip', %s, false), set_config('app.requisicao_id', %s, false)",
            [str(usuario_id or ""), ip or "", requisicao_id or ""],
        )


def limpar_contexto() -> None:
    definir_contexto(None, None, None)


@contextmanager
def contexto(usuario_id: int | None, ip: str | None = None, requisicao_id: str | None = None
             ) -> Iterator[None]:
    definir_contexto(usuario_id, ip, requisicao_id)
    try:
        yield
    finally:
        limpar_contexto()


def auditar_tabela(tabela: str) -> RunSQL:
    """Operação de migração que passa a auditar `tabela`."""
    trigger = f"auditoria_{tabela}"
    return RunSQL(
        sql=(
            f'CREATE TRIGGER "{trigger}" AFTER INSERT OR UPDATE OR DELETE ON "{tabela}" '
            "FOR EACH ROW EXECUTE FUNCTION auditoria_registrar();"
        ),
        reverse_sql=f'DROP TRIGGER IF EXISTS "{trigger}" ON "{tabela}";',
    )


def _hash(anterior: str | None, linha: dict[str, str]) -> str:
    # Mesmo algoritmo do trigger: sha256(anterior || texto canônico da linha).
    texto = (anterior or "") + linha["conteudo"]
    return hashlib.sha256(texto.encode()).hexdigest()


def verificar_cadeia() -> tuple[bool, int, int | None]:
    """Recalcula a cadeia. Retorna (íntegra, total verificado, id do 1º elo quebrado)."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, hash_anterior, hash, auditoria_conteudo(e) FROM auditoria_evento e "
            "ORDER BY id"
        )
        anterior: str | None = None
        total = 0
        for id_, hash_anterior, hash_, conteudo in cur.fetchall():
            total += 1
            if hash_anterior != anterior or _hash(anterior, {"conteudo": conteudo}) != hash_:
                return False, total, id_
            anterior = hash_
    return True, total, None


def resumo_json(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)
