"""Erros da porta de IA, já classificados pelo que o chamador deve fazer com eles.

- `FalhaTemporaria` (provedor indisponível, limite de taxa, tempo esgotado): pode tentar de
  novo dentro do limite de tentativas; esgotado, vale o caminho determinístico;
- `FalhaDefinitiva` (configuração, pedido recusado pela API): repetir não resolve;
- `Recusa`: o modelo declinou (stop_reason `refusal`); vale o caminho determinístico;
- `SaidaInvalida`: a resposta não é o JSON do esquema (ou veio truncada): **falha**, nunca
  "aproveita o que der";
- `BloqueadoPorPolitica`: o pedido não pode ir a este provedor (documento ao provedor real —
  ADR 0041 —, entrada acima do limite, modo real no PREVIEW).

`str(erro)` é mensagem para a tela, sem dado pessoal nem trecho do pedido.
"""

from __future__ import annotations


class ErroIA(Exception):
    def __init__(self, mensagem: str, codigo: str = ""):
        super().__init__(mensagem)
        self.codigo = codigo or type(self).__name__.lower()


class FalhaTemporaria(ErroIA):
    def __init__(self, mensagem: str, codigo: str = "", espera_segundos: int | None = None):
        super().__init__(mensagem, codigo)
        self.espera_segundos = espera_segundos


class ProvedorIndisponivel(FalhaTemporaria):
    pass


class LimiteDeTaxa(FalhaTemporaria):
    pass


class TempoEsgotado(FalhaTemporaria):
    pass


class FalhaDefinitiva(ErroIA):
    pass


class ConfiguracaoIncompleta(FalhaDefinitiva):
    pass


class Recusa(ErroIA):
    pass


class SaidaInvalida(ErroIA):
    pass


class BloqueadoPorPolitica(ErroIA):
    pass
