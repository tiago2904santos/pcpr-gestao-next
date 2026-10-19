from django.apps import AppConfig


class CoffeeConfig(AppConfig):
    name = "gestao.coffee"
    label = "coffee"
    verbose_name = "Coffee Break"

    def ready(self) -> None:
        from . import (
            agenda,
            busca,
            navegacao,  # noqa: F401  (registra o módulo no menu)
        )

        agenda.registrar()
        busca.registrar()
        from . import pendencias
        pendencias.registrar()  # aba Pendências da Agenda
