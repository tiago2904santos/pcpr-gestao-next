from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sincronizar(sender, **kwargs):
    from .papeis import sincronizar_papeis

    sincronizar_papeis()


class IdentidadeConfig(AppConfig):
    name = "gestao.identidade"
    label = "identidade"
    verbose_name = "Identidade e acesso"

    def ready(self) -> None:
        # Depois de todas as migrações (permissões existem), alinha os papéis ao código.
        post_migrate.connect(_sincronizar, dispatch_uid="identidade.sincronizar_papeis")
