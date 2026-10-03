"""Erros do eProtocolo, com mensagem pronta para a tela (dizendo como resolver)."""

from __future__ import annotations


class ErroEprotocolo(Exception):
    """Base. Quem chama mostra `str(erro)` como aviso; o caso de uso segue."""


class ConfiguracaoIncompleta(ErroEprotocolo):
    pass


class EscritaBloqueada(ErroEprotocolo):
    """A trava de somente leitura está ligada (padrão) ou o ambiente não permite escrever."""


class Indisponivel(ErroEprotocolo):
    """Rede, tempo esgotado ou erro 5xx: tentar de novo mais tarde (a outbox repete)."""


class Recusado(ErroEprotocolo):
    """O eProtocolo recusou o pedido (4xx): credencial, escopo, IP ou dado inválido."""

    def __init__(self, mensagem: str, status: int):
        super().__init__(mensagem)
        self.status = status


class NaoEncontrado(Recusado):
    pass
