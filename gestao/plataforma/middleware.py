"""Middlewares da plataforma."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse

from . import auditoria

log = logging.getLogger(__name__)


def _ip(request: HttpRequest) -> str | None:
    # Atrás de proxy reverso confiável, o Nginx sobrescreve X-Real-IP.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


class ContextoAuditoriaMiddleware:
    """Informa ao PostgreSQL quem é o autor de cada mudança desta requisição.

    O trigger de auditoria lê esses valores; a limpeza no `finally` impede que
    o contexto vaze para a próxima requisição na mesma conexão persistente.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.requisicao_id = uuid.uuid4().hex  # type: ignore[attr-defined]
        usuario = getattr(request, "user", None)
        usuario_id = usuario.pk if usuario is not None and usuario.is_authenticated else None
        auditoria.definir_contexto(usuario_id, _ip(request), request.requisicao_id)  # type: ignore[attr-defined]
        try:
            response = self.get_response(request)
        finally:
            auditoria.limpar_contexto()
        response["X-Request-ID"] = request.requisicao_id  # type: ignore[attr-defined]
        return response


class MedicaoServidorMiddleware:
    """Expõe `Server-Timing` (app, db, consultas) para medir TTFB e custo de banco.

    O navegador mostra esses valores no DevTools e os testes de desempenho os
    leem para validar os orçamentos (docs/quality/performance-budgets.md).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        estatisticas = {"consultas": 0, "tempo_db": 0.0}

        def medir(execute, sql, params, many, context):
            inicio = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                estatisticas["consultas"] += 1
                estatisticas["tempo_db"] += time.perf_counter() - inicio

        inicio = time.perf_counter()
        with connection.execute_wrapper(medir):
            response = self.get_response(request)
        total_ms = (time.perf_counter() - inicio) * 1000
        db_ms = estatisticas["tempo_db"] * 1000
        consultas = int(estatisticas["consultas"])
        response["Server-Timing"] = (
            f'app;dur={total_ms:.1f}, db;dur={db_ms:.1f};desc="{consultas} consultas"'
        )
        orcamento = getattr(settings, "ORCAMENTO_SQL_POR_REQUISICAO", 25)
        if consultas > orcamento:
            log.warning("Orçamento SQL excedido em %s: %s consultas (limite %s)",
                        request.path, consultas, orcamento)
        return response
