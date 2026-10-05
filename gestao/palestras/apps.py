from django.apps import AppConfig


class PalestrasConfig(AppConfig):
    name = "gestao.palestras"
    label = "palestras"
    verbose_name = "Palestras e eventos"

    def ready(self) -> None:
        from . import agenda, navegacao  # noqa: F401  (registra o módulo no menu)
        agenda.registrar()
