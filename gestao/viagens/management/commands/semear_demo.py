"""Dataset DEMO populoso e determinístico do ambiente PREVIEW (docs/ops/preview.md).

Idempotente: apaga os dados de negócio e recria tudo igual (mesmo dia ⇒ mesmo dataset).
Bloqueado fora de PREVIEW (e TEST) por `ambiente.exigir_ambiente_de_demonstracao`.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 — só o próprio manage.py, argumentos fixos
import sys
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from gestao.plataforma import ambiente
from gestao.plataforma.auditoria import contexto
from gestao.viagens import demonstracao
from gestao.viagens.models import Oficio


class Command(BaseCommand):
    help = "Recria o dataset DEMO (centenas de ofícios fictícios). Somente PREVIEW."

    def add_arguments(self, parser):
        parser.add_argument("--escala", type=float, default=1.0,
                            help="Fração do volume padrão (1.0 ≈ 260 ofícios).")
        parser.add_argument("--sem-documentos", action="store_true",
                            help="Não gera os PDFs agora (ficam com o worker da outbox).")
        parser.add_argument("--processos", type=int, default=4,
                            help="Workers paralelos para gerar os PDFs.")
        parser.add_argument("--se-vazio", action="store_true",
                            help="Só semeia se ainda não houver ofícios (subida do contêiner).")

    def handle(self, *args, escala: float, sem_documentos: bool, processos: int,
               se_vazio: bool = False, **opts):
        ambiente.exigir_ambiente_de_demonstracao("semear_demo")
        if se_vazio and Oficio.objects.exists():
            self.stdout.write("Dataset DEMO já existe; nada a fazer (use resetar_demo para zerar).")
            return
        inicio = time.perf_counter()
        if ambiente.atual() == "preview":  # nos testes a pasta de mídia é compartilhada
            shutil.rmtree(Path(settings.MEDIA_ROOT) / "documentos", ignore_errors=True)
            shutil.rmtree(Path(settings.MEDIA_ROOT) / "assinados", ignore_errors=True)
        with contexto(usuario_id=None, requisicao_id="semear_demo"):
            demonstracao.semear(escala=escala)
        tempo_dados = time.perf_counter() - inicio
        tempo_pdf = 0.0
        if not sem_documentos:
            inicio_pdf = time.perf_counter()
            self._gerar_documentos(processos)
            with contexto(usuario_id=None, requisicao_id="semear_demo"):
                demonstracao.acertar_datas_dos_documentos()
                demonstracao.vias_assinadas_para_avaliar()
            with contexto(usuario_id=None, requisicao_id="semear_demo"):
                demonstracao.notificacoes_para_avaliar()
            tempo_pdf = time.perf_counter() - inicio_pdf
        self._relatorio(demonstracao.resumo(), tempo_dados, tempo_pdf)

    def _gerar_documentos(self, processos: int) -> None:
        """Vários `processar_outbox --uma-vez` em paralelo (SKIP LOCKED divide o trabalho)."""
        comando = [sys.executable, str(Path(settings.BASE_DIR) / "manage.py"),
                   "processar_outbox", "--uma-vez"]
        workers = [subprocess.Popen(comando, env=os.environ.copy(),  # noqa: S603  # nosec B603
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                   for _ in range(max(1, processos))]
        for worker in workers:
            worker.wait()

    def _relatorio(self, r: demonstracao.Resultado, tempo_dados: float, tempo_pdf: float):
        linhas = [
            "Dataset DEMO criado (100% fictício).",
            "  " + " · ".join(f"{k}: {v}" for k, v in r.contagens.items()),
            "  ofícios por situação: " + ", ".join(
                f"{k} {v}" for k, v in sorted(r.por_situacao.items())),
            "  ofícios por ano: " + ", ".join(f"{k} {v}" for k, v in r.por_ano.items()),
            "  ofícios por unidade: " + ", ".join(
                f"{k} {v}" for k, v in sorted(r.por_unidade.items(), key=lambda i: -i[1])),
            f"  documentos ainda gerando: {r.documentos_pendentes}",
            f"  tempo: dados {tempo_dados:.1f}s · PDFs {tempo_pdf:.1f}s",
            "  Entrada: abra /conta/entrar/, deixe os campos vazios e clique em Entrar "
            "(usuário 'demo').",
        ]
        self.stdout.write(self.style.SUCCESS("\n".join(linhas)))
