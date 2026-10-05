from django.apps import AppConfig


class PalestrasConfig(AppConfig):
    name = "gestao.palestras"
    label = "palestras"
    verbose_name = "Palestras e eventos"

    def ready(self) -> None:
        from . import agenda, busca, conflitos, navegacao  # noqa: F401  (menu)
        agenda.registrar()
        busca.registrar()
        conflitos.registrar()
