from django.apps import AppConfig


class ViagensConfig(AppConfig):
    name = "gestao.viagens"
    label = "viagens"
    verbose_name = "Viagens"

    def ready(self) -> None:
        from . import (
            assinantes,  # noqa: F401  (assinantes da outbox)
            navegacao,  # noqa: F401  (registra o módulo no menu)
        )
