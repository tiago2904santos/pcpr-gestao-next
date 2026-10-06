from django.apps import AppConfig


class EventosConfig(AppConfig):
    name = "gestao.eventos"
    label = "eventos"
    verbose_name = "Eventos Sociais"

    def ready(self) -> None:
        from . import agenda, conflitos, navegacao  # noqa: F401  (menu)
        agenda.registrar()
        conflitos.registrar()
