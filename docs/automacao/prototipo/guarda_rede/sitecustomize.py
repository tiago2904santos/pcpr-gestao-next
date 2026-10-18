"""Guarda de rede dos processos do PCPR real no teste com o n8n (runserver e suíte).

Carregado automaticamente pelo Python (`sitecustomize`) quando esta pasta está no
`PYTHONPATH`. Recusa a resolução de qualquer nome que não seja do próprio host: se algum
caminho do PCPR tentar falar com a Meta (a base da Graph API é fixa em
`gestao/integracoes/whatsapp/config.py`), com a Anthropic ou com qualquer outro serviço, a
chamada falha localmente ANTES de sair (DNS recusado = "não enviado"). Cada tentativa
bloqueada é anotada em `PCPR_GUARDA_LOG` (só o nome do host, nunca corpo nem cabeçalho).

O PostgreSQL (libpq, código C) não passa por aqui e usa 127.0.0.1.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

PERMITIDOS = {"127.0.0.1", "localhost", "::1", ""}
_original = socket.getaddrinfo
_trava = threading.Lock()


def _anotar(host: str) -> None:
    caminho = os.environ.get("PCPR_GUARDA_LOG")
    if not caminho:
        return
    with _trava, Path(caminho).open("a", encoding="utf-8") as f:
        f.write(f"{time.time():.3f}\t{os.getpid()}\t{host}\n")


def _guardado(host, *args, **kwargs):
    nome = host.decode() if isinstance(host, bytes) else str(host or "")
    if nome.lower() not in PERMITIDOS:
        _anotar(nome)
        raise socket.gaierror(socket.EAI_NONAME, f"guarda de rede do teste: {nome} bloqueado")
    return _original(host, *args, **kwargs)


def instalar() -> None:
    if socket.getaddrinfo is not _guardado:
        socket.getaddrinfo = _guardado


if os.environ.get("PCPR_GUARDA_REDE") == "1":
    instalar()
