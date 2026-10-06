from django.apps import AppConfig


class CoffeeConfig(AppConfig):
    name = "gestao.coffee"
    label = "coffee"
    verbose_name = "Coffee Break"

    def ready(self) -> None:
        from . import navegacao  # noqa: F401  (registra o módulo no menu)
