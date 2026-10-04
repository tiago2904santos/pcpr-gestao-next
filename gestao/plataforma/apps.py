from django.apps import AppConfig


class PlataformaConfig(AppConfig):
    name = "gestao.plataforma"
    label = "plataforma"
    verbose_name = "Plataforma"

    def ready(self) -> None:
        from . import checks, notificacoes  # noqa: F401  (notificacoes: assinante da outbox)
        from .ambiente import exigir_demo_somente_no_preview

        # Vale para qualquer processo (gunicorn, worker, shell), não só para `check`.
        exigir_demo_somente_no_preview()
