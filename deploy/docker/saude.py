"""Health check do contêiner web: GET /saude/ como se viesse do proxy HTTPS.

Com SECURE_SSL_REDIRECT e ALLOWED_HOSTS restritos, um GET cru em 127.0.0.1 receberia 301
ou 400; por isso enviamos o Host público e X-Forwarded-Proto: https (mesmo que o proxy).
"""

import os
import sys
import urllib.request

hosts = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
host = (hosts[0] if hosts else "localhost").lstrip(".")
pedido = urllib.request.Request(
    "http://127.0.0.1:8000/saude/",
    headers={"Host": host, "X-Forwarded-Proto": "https", "User-Agent": "pcpr-healthcheck"},
)
try:
    with urllib.request.urlopen(pedido, timeout=4) as resposta:  # noqa: S310  # nosec B310
        sys.exit(0 if resposta.status == 200 else 1)
except Exception as exc:
    sys.stderr.write(f"saude: {exc}\n")
    sys.exit(1)
