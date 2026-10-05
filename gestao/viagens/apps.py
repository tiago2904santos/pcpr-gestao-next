from django.apps import AppConfig


class ViagensConfig(AppConfig):
    name = "gestao.viagens"
    label = "viagens"
    verbose_name = "Viagens"

    def ready(self) -> None:
        from gestao.plataforma.rotinas import registrar_rotina

        from . import (
            assinantes,  # noqa: F401  (assinantes da outbox)
            avisos,
            navegacao,  # noqa: F401  (registra o módulo no menu)
        )
        registrar_rotina("avisos da prestação de contas", avisos.avisar_prazos)
        registrar_rotina("chegadas de viagem", avisos.avisar_chegadas)

        from . import agenda, busca, conflitos
        agenda.registrar()
        busca.registrar()
        conflitos.registrar()
