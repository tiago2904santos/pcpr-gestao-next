from django.apps import AppConfig


class AutomacaoConfig(AppConfig):
    name = "gestao.automacao"
    label = "automacao"
    verbose_name = "Automação e WhatsApp"

    def ready(self) -> None:
        from gestao.plataforma import recursos

        from . import checks, ferramentas_padrao, navegacao, tipos  # noqa: F401
        from .rotinas import registrar

        # Automações desligadas (ADR 0050): telas, API e webhook do WhatsApp respondem 404. Os
        # links pessoais (/p/) seguem: o envio manual leva o link de KM no texto.
        for namespace in ("automacao", "api_automacao", "integracoes_whatsapp"):
            recursos.registrar_rotas(namespace, recursos.AUTOMACAO)

        tipos.registrar()
        ferramentas_padrao.registrar()
        registrar()
        from . import pendencias
        pendencias.registrar()  # aba Pendências da Agenda
