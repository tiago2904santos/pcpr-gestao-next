"""API Python da trilha de auditoria mantida pelo banco.

- `contexto(...)` informa ao PostgreSQL quem está agindo (lido pelo trigger);
- `auditar_tabela(...)` gera o SQL que liga o trigger a uma tabela (usado em
  migrações via `migrations.RunSQL`);
- `verificar_cadeia()` recalcula a cadeia de hashes;
- `passos_do_registro(...)` lê a trilha de um registro para a linha do tempo da tela.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

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
    """Quem age durante o bloco; ao sair, volta o contexto de antes (um bloco aninhado —
    ex.: uma ação da semeadura DEMO — não apaga o de fora)."""
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.usuario_id', true), "
                    "current_setting('app.ip', true), current_setting('app.requisicao_id', true)")
        antes = cur.fetchone() or ("", "", "")
    definir_contexto(usuario_id, ip, requisicao_id)
    try:
        yield
    finally:
        anterior_usuario = int(antes[0]) if antes[0] and str(antes[0]).isdecimal() else None
        definir_contexto(anterior_usuario, antes[1] or None, antes[2] or None)


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


@dataclass
class Passo:
    """Uma ação vista na trilha: o que uma requisição mudou num registro e nas suas filhas."""

    em: datetime
    usuario_id: int | None
    operacao: str  # INSERT | UPDATE | DELETE (da linha principal)
    campos: set[str] = field(default_factory=set)
    filhas: set[str] = field(default_factory=set)
    antes: dict = field(default_factory=dict)
    depois: dict = field(default_factory=dict)
    usuario: object | None = None


def passos_do_registro(tabela: str, registro_id: int | str,
                       filhas: dict[str, str] | None = None, limite: int = 60,
                       marcos: tuple[str, ...] = ()) -> list[Passo]:
    """Linha do tempo de um registro lida da trilha (somente leitura), do mais novo ao mais
    antigo. Eventos da mesma requisição viram um passo só.

    - `filhas`: {tabela filha: coluna que aponta para o registro} (destinos, equipe…); entram
      como nomes em `Passo.filhas` quando a mesma requisição mexeu nelas *deste* registro;
    - `limite`: os eventos mais recentes da tabela principal (o autosave gera muitos);
    - `marcos`: campos cuja mudança sempre entra, além do nascimento (INSERT), por mais
      antiga que seja (ex.: situação, primeira geração do documento).
    """
    from functools import reduce
    from operator import or_

    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from .models import EventoAuditoria

    do_registro = EventoAuditoria.objects.filter(tabela=tabela, registro_id=str(registro_id))
    recentes = list(do_registro.order_by("-id")[:limite])
    sempre = Q(operacao="INSERT") | reduce(or_, (Q(alterados__contains=[c]) for c in marcos),
                                           Q(pk__in=[]))
    vistos = {e.pk for e in recentes}
    principais = sorted(recentes + [e for e in do_registro.filter(sempre) if e.pk not in vistos],
                        key=lambda e: e.pk, reverse=True)
    requisicoes = {e.requisicao_id for e in principais if e.requisicao_id}
    tocadas: dict[str, set[str]] = {}
    if filhas and requisicoes:
        deste = reduce(or_, (Q(tabela=tab) & (Q(**{f"depois__{fk}": int(registro_id)})
                                               | Q(**{f"antes__{fk}": int(registro_id)}))
                             for tab, fk in filhas.items()))
        for req, tab in EventoAuditoria.objects.filter(
                deste, requisicao_id__in=requisicoes).values_list(
                "requisicao_id", "tabela").distinct():
            tocadas.setdefault(req or "", set()).add(tab)
    passos: list[Passo] = []
    por_requisicao: dict[str, Passo] = {}
    for e in principais:  # do mais novo ao mais antigo
        passo = por_requisicao.get(e.requisicao_id or "")
        if passo is None:
            passo = Passo(em=e.ocorrido_em, usuario_id=e.usuario_id, operacao=e.operacao,
                          antes=e.antes or {}, depois=e.depois or {},
                          filhas=set(tocadas.get(e.requisicao_id or "", set())))
            passos.append(passo)
            if e.requisicao_id:
                por_requisicao[e.requisicao_id] = passo
        else:  # evento mais antigo da mesma requisição: o "antes" é o dele
            passo.antes = e.antes or {}
            if e.operacao == "INSERT":
                passo.operacao = "INSERT"
        passo.campos.update(e.alterados or [])
    # O INSERT mais recente é o nascimento deste registro: o que vem antes dele é de outro
    # registro que teve o mesmo id (excluído, com a sequência reiniciada — ex.: base DEMO).
    nascimento = next((i for i, p in enumerate(passos) if p.operacao == "INSERT"), None)
    if nascimento is not None:
        passos = passos[:nascimento + 1]
    usuarios = get_user_model().objects.in_bulk({p.usuario_id for p in passos if p.usuario_id})
    for p in passos:
        p.usuario = usuarios.get(p.usuario_id) if p.usuario_id else None
    return passos
