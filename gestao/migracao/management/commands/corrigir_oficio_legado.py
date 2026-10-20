"""Passo de PRODUÇÃO da correção de um ofício migrado (ver `gestao.migracao.correcao`).

    python manage.py corrigir_oficio_legado --arquivo /restauro/correcao-oficio-126.json
    python manage.py corrigir_oficio_legado --arquivo /restauro/correcao-oficio-126.json --gravar

Na VPS o contêiner de tarefa só monta a mídia; o JSON entra por um volume só de leitura:

    pcpr.sh producao compose run --rm -T -v /root/correcao:/correcao:ro tarefa \
        corrigir_oficio_legado --arquivo /correcao/correcao-oficio-126.json [--gravar]

Antes: copiar os PDFs listados no JSON (`midia[].destino`) para o MEDIA_ROOT, no mesmo caminho
(na VPS, `/srv/pcpr/producao/dados/midia/legado/gv/…`, dono 10001).
Sem `--gravar` é um ensaio: confere tudo, aplica e desfaz. Recusa se o ofício mudou desde a
exportação, se falta um id citado ou um PDF. Aplicar de novo não faz nada. A saída só tem ids,
nomes de campos e contagens.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...correcao import CorrecaoRecusada, executar, resumo


class Command(BaseCommand):
    help = "Aplica a um ofício migrado a versão do GV exportada por exportar_oficio_legado."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", required=True)
        parser.add_argument("--gravar", action="store_true")

    def handle(self, *args, **o):
        if os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "sim"):
            raise CommandError("DEMO_MODE ligado: dados reais nunca entram no PREVIEW.")
        dados = json.loads(Path(o["arquivo"]).read_text(encoding="utf-8"))
        try:
            plano, docs = executar(dados, gravar=o["gravar"])
        except CorrecaoRecusada as erro:
            raise CommandError(str(erro)) from erro
        for linha in resumo(dados, plano):
            self.stdout.write(linha)
        if plano.problemas:
            raise CommandError(f"{len(plano.problemas)} problema(s): nada foi gravado.")
        if plano.ja_aplicada:
            return
        if o["gravar"]:
            self.stdout.write(f"GRAVADO: ofício {plano.alvo.pk} corrigido; documentos {docs}")
        else:
            self.stdout.write("ENSAIO (nada gravado): rode de novo com --gravar para aplicar")
