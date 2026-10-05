from django.apps import AppConfig


class ImprensaConfig(AppConfig):
    name = "gestao.imprensa"
    label = "imprensa"
    verbose_name = "Atendimento à imprensa"

    def ready(self) -> None:
        from . import agenda, navegacao  # noqa: F401  (registra o módulo no menu)
        agenda.registrar()
