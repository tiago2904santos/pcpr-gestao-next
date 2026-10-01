from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    name = "gestao.plataforma"
    label = "plataforma"
    verbose_name = "Plataforma"

    def ready(self) -> None:
        from . import checks  # noqa: F401
