from django.apps import AppConfig


class EventosConfig(AppConfig):
    name = "gestao.eventos"
    label = "eventos"
    verbose_name = "Eventos Sociais"

    def ready(self) -> None:
        from . import agenda, conflitos, navegacao  # noqa: F401  (menu)
        agenda.registrar()
        conflitos.registrar()
        from gestao.plataforma.rotinas import registrar_rotina

        from .lembretes import enviar_lembretes
        registrar_rotina("lembretes das solicitações de evento", enviar_lembretes)
