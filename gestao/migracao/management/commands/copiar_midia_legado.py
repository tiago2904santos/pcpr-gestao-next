"""Copia os binários dos sistemas antigos para os nomes que a migração gravou no banco.

    python manage.py copiar_midia_legado \
        --midia-ev /restauro/02-eventos-sociais/arquivos/media \
        --midia-gv /restauro/01-gerenciador-viagens/arquivos/media \
        [--destino /pasta/da/midia] [--gravar]

A migração (`importar_legado`) grava só a referência, endereçada pelo conteúdo:
`legado/<ev|gv>/<2 primeiros do sha256>/<sha256>.<ext>` (ver `etapas/comum.py`). Aqui se lê do
banco todo nome `legado/…` de todos os `FileField`, calcula-se o SHA-256 de cada arquivo dos dois
backups e copia-se o conteúdo certo para `<destino>/<nome>` (padrão: `MEDIA_ROOT`), conferindo o
hash depois de copiar. Sem `--gravar` só conta. Rodar de novo não copia o que já está certo.
Nada de nome de pessoa nem de conteúdo na saída: só contagens e nomes que são hashes.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models

PREFIXO = "legado/"


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def nomes_no_banco() -> set[str]:
    """Todo valor `legado/…` de todo FileField/ImageField dos modelos instalados."""
    nomes: set[str] = set()
    for modelo in apps.get_models():
        campos = [f.name for f in modelo._meta.concrete_fields if isinstance(f, models.FileField)]
        for campo in campos:
            filtro = {f"{campo}__startswith": PREFIXO}
            nomes.update(modelo._default_manager.filter(**filtro)
                         .values_list(campo, flat=True).distinct())
    return nomes


def indexar(raizes: list[Path]) -> dict[str, Path]:
    """sha256 → um arquivo com esse conteúdo (o primeiro encontrado)."""
    indice: dict[str, Path] = {}
    for raiz in raizes:
        for pasta, _, arquivos in os.walk(raiz):
            for nome in arquivos:
                p = Path(pasta) / nome
                if p.is_file():
                    indice.setdefault(sha256_de(p), p)
    return indice


class Command(BaseCommand):
    help = "Copia a mídia dos sistemas antigos para os nomes gravados pela migração."

    def add_arguments(self, parser):
        parser.add_argument("--midia-ev", required=True)
        parser.add_argument("--midia-gv", default="")
        parser.add_argument("--destino", default="")
        parser.add_argument("--gravar", action="store_true")

    def handle(self, *args, **o):
        raizes = [Path(r) for r in (o["midia_ev"], o["midia_gv"]) if r]
        for r in raizes:
            if not r.is_dir():
                raise CommandError(f"Pasta de mídia inexistente: {r}")
        destino = Path(o["destino"] or settings.MEDIA_ROOT)
        nomes = nomes_no_banco()
        indice = indexar(raizes)
        n: Counter[str] = Counter()
        faltando: list[str] = []
        for nome in sorted(nomes):
            sha = Path(nome).stem
            alvo = destino / nome
            if alvo.is_file() and sha256_de(alvo) == sha:
                n["ja_presente"] += 1
                continue
            origem = indice.get(sha)
            if origem is None:
                n["ausente_no_backup"] += 1
                faltando.append(nome)
                continue
            if not o["gravar"]:
                n["a_copiar"] += 1
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            temporario = alvo.with_name(alvo.name + ".parcial")
            shutil.copyfile(origem, temporario)
            if sha256_de(temporario) != sha:
                temporario.unlink()
                raise CommandError(f"Cópia corrompida: {nome}")
            temporario.replace(alvo)
            n["copiado"] += 1
        usados = {Path(x).stem for x in nomes}
        n["no_backup_sem_referencia"] = sum(1 for sha in indice if sha not in usados)
        self.stdout.write(f"referências no banco: {len(nomes)}; arquivos distintos nos backups: "
                          f"{len(indice)}; destino: {destino}")
        for chave in sorted(n):
            self.stdout.write(f"  {chave}: {n[chave]}")
        for nome in faltando[:50]:
            self.stdout.write(f"  ausente: {nome}")
        if not o["gravar"]:
            self.stdout.write("Ensaio: nada foi copiado (use --gravar).")
