"""Leitura dos bancos antigos (somente leitura, transação READ ONLY)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
from psycopg import sql as psql
from psycopg.rows import dict_row


class Fonte:
    """Um banco antigo. `linhas()` devolve dicionários; nada é escrito lá."""

    def __init__(self, sistema: str, url: str):
        self.sistema = sistema
        self.conexao = psycopg.connect(url, row_factory=dict_row, autocommit=False)
        with self.conexao.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")

    def linhas(self, sql: str, params: Any = None) -> list[dict]:
        with self.conexao.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def iterar(self, sql: str, params: Any = None) -> Iterator[dict]:
        yield from self.linhas(sql, params)

    def valor(self, sql: str, params: Any = None) -> Any:
        linhas = self.linhas(sql, params)
        return next(iter(linhas[0].values())) if linhas else None

    def tabela(self, nome: str) -> list[dict]:
        """Todas as linhas de uma tabela, na ordem da chave; [] se ela não existe."""
        if not self.tem_tabela(nome):
            return []
        consulta = psql.SQL("SELECT * FROM {} ORDER BY 1").format(psql.Identifier(nome))
        with self.conexao.cursor() as cur:
            cur.execute(consulta)
            return list(cur.fetchall())

    def tem_tabela(self, nome: str) -> bool:
        return bool(self.valor("SELECT to_regclass(%s) IS NOT NULL AS ok", [f"public.{nome}"]))

    def fechar(self) -> None:
        self.conexao.rollback()
        self.conexao.close()
