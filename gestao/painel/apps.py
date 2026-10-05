from django.apps import AppConfig


class PainelConfig(AppConfig):
    name = "gestao.painel"
    label = "painel"
    verbose_name = "Painel"

    def ready(self) -> None:
        from . import navegacao  # noqa: F401  (registra a Agenda no menu)
