from django.apps import AppConfig


class MigracaoConfig(AppConfig):
    name = "gestao.migracao"
    verbose_name = "Migração dos sistemas antigos"
    default_auto_field = "django.db.models.BigAutoField"
