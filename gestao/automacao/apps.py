from django.apps import AppConfig


class AutomacaoConfig(AppConfig):
    name = "gestao.automacao"
    label = "automacao"
    verbose_name = "Automação e WhatsApp"

    def ready(self) -> None:
        from . import checks, ferramentas_padrao, navegacao, tipos  # noqa: F401
        from .rotinas import registrar

        tipos.registrar()
        ferramentas_padrao.registrar()
        registrar()
        from . import pendencias
        pendencias.registrar()  # aba Pendências da Agenda
