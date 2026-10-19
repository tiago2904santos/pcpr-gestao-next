"""HTTPS para o provedor de IA, injetável (os testes nunca tocam a rede).

Sempre TLS verificado, sem seguir redirecionamento (um 3xx levaria a chave para outro
endereço) e com teto de leitura. Falhou antes de o pedido sair → `NaoEnviado`; depois →
`TalvezEnviado` (para a IA, repetir só custa tokens: o chamador conta como tentativa).
"""

from __future__ import annotations

import http.client
import ssl
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field


class NaoEnviado(Exception):
    pass


class TalvezEnviado(Exception):
    pass


@dataclass(frozen=True)
class Resposta:
    status: int
    corpo: bytes
    cabecalhos: dict[str, str] = field(default_factory=dict)
    truncada: bool = False


#: (método, url, cabeçalhos, corpo, timeout, limite de leitura) -> Resposta
Transporte = Callable[[str, str, dict[str, str], bytes | None, float, int], Resposta]


def transporte_https(metodo: str, url: str, cabecalhos: dict[str, str], corpo: bytes | None,
                     timeout: float, limite: int) -> Resposta:
    partes = urllib.parse.urlsplit(url)
    if partes.scheme != "https" or not partes.hostname:
        raise NaoEnviado("Só HTTPS.")
    caminho = (partes.path or "/") + (f"?{partes.query}" if partes.query else "")
    conexao = http.client.HTTPSConnection(partes.hostname, partes.port or 443, timeout=timeout,
                                          context=ssl.create_default_context())
    try:
        try:
            conexao.connect()
        except (OSError, ssl.SSLError) as erro:
            raise NaoEnviado(type(erro).__name__) from erro
        try:
            conexao.request(metodo, caminho, body=corpo, headers=cabecalhos)
            resposta = conexao.getresponse()
            bruto = resposta.read(limite + 1)
        except (OSError, http.client.HTTPException) as erro:
            raise TalvezEnviado(type(erro).__name__) from erro
        return Resposta(status=resposta.status, corpo=bruto[:limite],
                        cabecalhos={k.lower(): v for k, v in resposta.getheaders()},
                        truncada=len(bruto) > limite)
    finally:
        conexao.close()


class TransporteGravado:
    """Respostas gravadas, na ordem: cada item é uma `Resposta` ou uma exceção a lançar.
    Guarda as chamadas para o teste conferir o que teria saído."""

    def __init__(self, respostas: list[Resposta | Exception]):
        self.respostas = list(respostas)
        self.chamadas: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def __call__(self, metodo: str, url: str, cabecalhos: dict[str, str], corpo: bytes | None,
                 timeout: float, limite: int) -> Resposta:
        self.chamadas.append((metodo, url, dict(cabecalhos), corpo))
        if not self.respostas:
            raise AssertionError("Chamada sem resposta gravada: o teste não esperava rede.")
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return Resposta(item.status, item.corpo[:limite], item.cabecalhos,
                        len(item.corpo) > limite)
