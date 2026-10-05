from django.apps import AppConfig


class EventosConfig(AppConfig):
    name = "gestao.eventos"
    label = "eventos"
    verbose_name = "Eventos Sociais"

    def ready(self) -> None:
        from . import navegacao  # noqa: F401  (registra o módulo no menu)
