from django.apps import AppConfig


class PublicacoesConfig(AppConfig):
    name = "gestao.publicacoes"
    label = "publicacoes"
    verbose_name = "Publicações"

    def ready(self) -> None:
        from . import agenda, busca, navegacao  # noqa: F401  (registra o módulo no menu)
        agenda.registrar()
        busca.registrar()
