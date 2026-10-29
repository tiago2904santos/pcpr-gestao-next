"""Erros do canal WhatsApp, já classificados pelo que o PCPR deve fazer com eles.

A classificação segue o `code` da Meta (nunca o status HTTP nem o título — tabela da seção 6
de docs/integrations/whatsapp-cloud-api-referencia.md):

- `FalhaTemporaria`: a mensagem com certeza NÃO saiu; pode tentar de novo depois (backoff);
- `FalhaDefinitiva`: não saiu e repetir não resolve (número sem WhatsApp, modelo inexistente,
  fora da janela de 24 h sem modelo…);
- `ResultadoIncerto`: não dá para saber se saiu (tempo esgotado depois de enviar, conexão
  caída, 5xx sem corpo de erro). Nunca se reenvia às cegas: vai para revisão humana;
- `CanalBloqueado`: a conta/credencial está com problema (token vencido, conta restrita,
  pagamento): para tudo e avisa quem administra.
"""

from __future__ import annotations


class ErroWhatsapp(Exception):
    """Base. `codigo` é o código da Meta (ou um nosso, em minúsculas); `str(erro)` é a
    mensagem para a tela, sem dado pessoal."""

    def __init__(self, mensagem: str, codigo: str = ""):
        super().__init__(mensagem)
        self.codigo = codigo


class ConfiguracaoIncompleta(ErroWhatsapp):
    pass


class FalhaTemporaria(ErroWhatsapp):
    def __init__(self, mensagem: str, codigo: str = "", espera_segundos: int | None = None):
        super().__init__(mensagem, codigo)
        self.espera_segundos = espera_segundos


class FalhaDefinitiva(ErroWhatsapp):
    pass


class ResultadoIncerto(ErroWhatsapp):
    pass


class CanalBloqueado(FalhaDefinitiva):
    """Problema da conta ou da credencial: nenhuma mensagem deve sair até alguém olhar."""


class MidiaInvalida(ErroWhatsapp):
    """Arquivo recebido grande demais, de tipo não aceito, corrompido ou com hash divergente."""


class PayloadInvalido(ErroWhatsapp):
    """Corpo de webhook que não é o JSON esperado (malformado, grande demais, de outro objeto)."""


#: Códigos da Meta (seção 6 da referência) → o que fazer.
TEMPORARIOS = frozenset({"130429", "131056", "131057", "131000", "131016", "1", "2", "80007",
                         "4"})
BLOQUEIO_DE_CONTA = frozenset({"0", "190", "368", "131031", "131042", "131064", "10", "3",
                               "131005", "200"})
FORA_DA_JANELA = "131047"
