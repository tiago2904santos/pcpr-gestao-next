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

        from . import comunicacoes  # WhatsApp: aviso de diárias e comprovante (ADR 0047)
        comunicacoes.registrar()
        from . import ferramentas_automacao  # ferramentas tipadas para a automação (ADR 0020)
        ferramentas_automacao.registrar()
        from . import proposta  # prévia consolidada como ferramenta de leitura (AUT-14)
        proposta.registrar_ferramentas()
        from . import comunicacoes_viagem  # WhatsApp: link de km e avisos à equipe (10-4, 10-2)
        comunicacoes_viagem.registrar()
        registrar_rotina("links de km na véspera (WhatsApp)", comunicacoes_viagem.agendar_links_km)
        registrar_rotina("lembretes de km (WhatsApp)", comunicacoes_viagem.agendar_lembretes_km)
        registrar_rotina("lembretes de comprovante (WhatsApp)", comunicacoes.agendar_lembretes)

        from . import envios_manuais
        registrar_rotina("pendências de envio manual", envios_manuais.sincronizar)

        from . import agenda, busca, conflitos, de_eventos
        agenda.registrar()
        busca.registrar()
        conflitos.registrar()
        de_eventos.registrar()  # a viagem que nasce da solicitação de evento (E4)
