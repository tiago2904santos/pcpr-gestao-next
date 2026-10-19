"""Diagnóstico do canal WhatsApp.

    python manage.py whatsapp_check          # configuração, sem tocar a rede
    python manage.py whatsapp_check --ping   # consulta o número na Graph API (só leitura)

Nunca envia mensagem e nunca mostra segredo (ids mascarados, token só "configurado").
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from gestao.integracoes.whatsapp import config, servico
from gestao.integracoes.whatsapp.adaptadores import AdaptadorCloudApi, _json
from gestao.integracoes.whatsapp.transporte import NaoEnviado, TalvezEnviado


class Command(BaseCommand):
    help = "Mostra a configuração do WhatsApp; com --ping, lê os dados do número (sem enviar)."

    def add_arguments(self, parser):
        parser.add_argument("--ping", action="store_true",
                            help="GET do número de telefone na Graph API (não envia nada).")

    def handle(self, *args, ping: bool = False, **opcoes):
        for chave, valor in servico.diagnostico().items():
            self.stdout.write(f"{chave:>22}: {valor}")
        if not ping:
            return
        c = config.carregar()
        if not c.real:
            self.stdout.write(self.style.WARNING("ping: o canal está simulado; nada a consultar."))
            return
        porta = AdaptadorCloudApi(c)
        url = porta._url(c.phone_number_id,
                         fields="display_phone_number,verified_name,quality_rating")
        try:
            resposta = porta._chamar("GET", url, None, c.timeout_envio)
        except (NaoEnviado, TalvezEnviado) as erro:
            self.stdout.write(self.style.WARNING(f"ping: sem conexão ({erro})"))
            return
        dados = _json(resposta.corpo)
        if resposta.status >= 400:
            codigo = (dados.get("error") or {}).get("code", resposta.status)
            self.stdout.write(self.style.WARNING(f"ping: recusado (código {codigo})"))
            return
        self.stdout.write(self.style.SUCCESS(
            f"ping: ok — {dados.get('verified_name', '?')} · qualidade "
            f"{dados.get('quality_rating', '?')}"))
