"""Diagnóstico da integração com o eProtocolo.

    python manage.py eprotocolo_check          # configuração, sem tocar a rede
    python manage.py eprotocolo_check --ping   # autentica e faz uma consulta de leitura

Nunca grava nada no eProtocolo e nunca mostra segredo (id e consumer mascarados).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from gestao.integracoes.eprotocolo import servico
from gestao.integracoes.eprotocolo.erros import ErroEprotocolo


class Command(BaseCommand):
    help = "Mostra a configuração do eProtocolo; com --ping, autentica e consulta."

    def add_arguments(self, parser):
        parser.add_argument("--ping", action="store_true",
                            help="Autentica e consulta um protocolo (somente leitura).")
        parser.add_argument("--protocolo", default="000000000",
                            help="Número usado no --ping (9 dígitos).")

    def handle(self, *args, ping: bool = False, protocolo: str = "", **opcoes):
        for chave, valor in servico.diagnostico().items():
            self.stdout.write(f"{chave:>18}: {valor}")
        if not ping:
            return
        try:
            porta = servico.adaptador()
            porta.autenticar()
            situacao = porta.consultar(protocolo)
        except ErroEprotocolo as erro:
            self.stdout.write(self.style.WARNING(f"ping: {erro}"))
            return
        self.stdout.write(self.style.SUCCESS(
            f"ping: ok — {situacao.numero}: {situacao.situacao} ({situacao.origem})"))
