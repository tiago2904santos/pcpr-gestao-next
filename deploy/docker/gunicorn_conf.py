"""Configuração do Gunicorn na implantação: o log de acesso não pode registrar o token do
feed ICS da agenda (`/agenda/ics/<token>.ics` — a única credencial do feed). Mesma regra do
filtro da aplicação (gestao/plataforma/logs.py), aplicada à linha de acesso do Gunicorn."""

from __future__ import annotations

import re

from gunicorn.glogging import Logger

PADRAO = re.compile(r"(/agenda/ics/)[^/\s'\"?]+")


class LoggerMascarado(Logger):
    def atoms(self, resp, req, environ, request_time):
        # Todos os átomos de texto: linha da requisição, caminho, Referer, variáveis do environ.
        return {chave: PADRAO.sub(r"\1[token]", valor) if isinstance(valor, str) else valor
                for chave, valor in super().atoms(resp, req, environ, request_time).items()}


logger_class = LoggerMascarado
