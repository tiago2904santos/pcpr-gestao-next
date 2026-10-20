"""Casos de uso do eProtocolo para os contextos de negócio.

Escolhe o adaptador pela configuração (simulado sem credencial; HTTP com credencial) e
garante as travas: escrita só com a trava aberta, origem do número sempre explícita.
"""

from __future__ import annotations

from gestao.plataforma import recursos

from . import config as cfg
from .adaptadores import AdaptadorHttp, AdaptadorSimulado
from .erros import Desligado
from .porta import Origem, PedidoDeAbertura, PortaEprotocolo, ProtocoloAberto, Situacao


def adaptador(configuracao: cfg.Configuracao | None = None) -> PortaEprotocolo:
    configuracao = configuracao or cfg.carregar()
    if configuracao.real:
        return AdaptadorHttp(configuracao)
    return AdaptadorSimulado()


def _exigir_ligado() -> None:
    if not recursos.ligado(recursos.EPROTOCOLO):
        raise Desligado("A integração com o eProtocolo está desligada. Digite o número do "
                        "protocolo à mão.")


def consultar(numero: str) -> Situacao:
    _exigir_ligado()
    return adaptador().consultar(numero)


def abrir(pedido: PedidoDeAbertura) -> ProtocoloAberto:
    _exigir_ligado()
    return adaptador().abrir(pedido)


def origem_vale_como_oficial(origem: str) -> bool:
    return origem in (Origem.EPROTOCOLO, Origem.MANUAL)


def diagnostico() -> dict[str, object]:
    """Resumo seguro (sem segredo) para o comando `eprotocolo_check`."""
    c = cfg.carregar()
    base, token = c.urls()
    return {
        "ambiente": c.ambiente,
        "estado": c.descricao(),
        "modo_real": c.real,
        "numero_oficial": c.oficial,
        "somente_leitura": c.somente_leitura,
        "escrita_liberada": c.escrita_liberada,
        "base_url": base or "(não configurada)",
        "token_url": token or "(não configurada)",
        "client_id": cfg.mascarar(c.client_id),
        "client_secret": "configurado" if c.client_secret else "(não configurado)",
        "consumer_id": cfg.mascarar(c.consumer_id),
        "escopos": " ".join(c.escopos),
        "faltam_para_real": c.faltantes(),
        "faltam_para_abrir": c.faltantes_para_abrir(),
    }
