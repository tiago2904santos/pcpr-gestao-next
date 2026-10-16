"""Worker persistente com claims curtos e conversões em processos isolados."""

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections

from gestao.plataforma import auditoria
from gestao.viagens.importacao import processar, reservar

log = logging.getLogger(__name__)


def uma():
    close_old_connections()
    try:
        pk = reservar()
        if pk is not None:
            try:
                from gestao.viagens.models import ArquivoImportado

                autor = ArquivoImportado.objects.get(pk=pk).usuario_id
                auditoria.definir_contexto(autor, None, f"importacao-{pk}")
                processar(pk)
            except Exception:
                # Lease permite retomar; log não contém texto dos documentos.
                log.exception("Falha interna ao processar importação %s", pk)
        return pk is not None
    finally:
        auditoria.limpar_contexto()
        connections.close_all()


class Command(BaseCommand):
    help = "Processa a fila de importação documental (conversão, OCR e anexação)."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true")
        parser.add_argument("--concorrencia", type=int, default=3)

    def handle(self, *args, **options):
        quantidade = min(4, max(1, options["concorrencia"]))
        parar = Event()

        def consumir():
            while not parar.is_set():
                if not uma():
                    if options["uma_vez"]:
                        return
                    parar.wait(1)

        with ThreadPoolExecutor(max_workers=quantidade) as pool:
            trabalhos = [pool.submit(consumir) for _ in range(quantidade)]
            try:
                for trabalho in trabalhos:
                    trabalho.result()
            finally:
                parar.set()
