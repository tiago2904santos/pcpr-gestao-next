"""Escolha do adaptador e diagnóstico seguro (sem segredo) do canal WhatsApp."""

from __future__ import annotations

from . import config as cfg
from .adaptadores import AdaptadorCloudApi, AdaptadorSimulado
from .porta import PortaWhatsapp


def adaptador(configuracao: cfg.Configuracao | None = None) -> PortaWhatsapp:
    """Cloud API só com tudo configurado e fora do PREVIEW; senão, simulado."""
    configuracao = configuracao or cfg.carregar()
    if configuracao.real:
        return AdaptadorCloudApi(configuracao)
    return AdaptadorSimulado()


def diagnostico() -> dict[str, object]:
    """Resumo para a tela de configuração e o comando `whatsapp_check` — nunca o segredo."""
    c = cfg.carregar()
    return {
        "modo": c.modo,
        "estado": c.descricao(),
        "modo_real": c.real,
        "versao": c.versao,
        "phone_number_id": cfg.mascarar(c.phone_number_id),
        "waba_id": cfg.mascarar(c.waba_id),
        "access_token": "configurado" if c.access_token else "(não configurado)",
        "app_secret": "configurado" if c.app_secret else "(não configurado)",
        "verify_token": "configurado" if c.verify_token else "(não configurado)",
        "lista_fechada": c.lista_fechada,
        "limite_por_hora": c.limite_por_hora,
        "remetente": c.remetente,
        "modelos": {tipo: f"{m.nome} ({m.idioma})" for tipo, m in sorted(c.modelos.items())},
        "faltam_para_real": c.faltantes(),
        "bloqueado_no_ambiente": c.bloqueado_no_ambiente,
    }
