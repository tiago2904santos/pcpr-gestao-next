"""Passo LOCAL da correção de um ofício migrado (ver `gestao.migracao.correcao`).

    python manage.py exportar_oficio_legado --gv-oficio 158 \
        --ev "$LEGADO_EV_URL" --gv "$LEGADO_GV_URL" \
        --midia-ev /restauro/02-eventos-sociais/arquivos/media \
        --midia-gv /restauro/01-gerenciador-viagens/arquivos/media \
        --saida /restauro/correcao-oficio-126.json --midia-saida /restauro/midia-correcao

Lê os bancos antigos (somente leitura) e o banco do destino de onde a produção foi carregada
(nada é gravado nele: a leitura roda numa transação desfeita). Grava o JSON (tem dados pessoais:
fica FORA do Git) e copia os PDFs para `--midia-saida/<nome endereçado pelo conteúdo>`.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...contexto import Contexto, Relatorio
from ...correcao import CorrecaoRecusada, Ensaio, copiar_midia, exportar, serializar
from ...fonte import Fonte


class Command(BaseCommand):
    help = "Exporta a versão do GV de um ofício já migrado, para corrigi-lo em produção."

    def add_arguments(self, parser):
        parser.add_argument("--gv-oficio", required=True, help="id do ofício no GV")
        parser.add_argument("--ev", default=os.environ.get("LEGADO_EV_URL", ""))
        parser.add_argument("--gv", default=os.environ.get("LEGADO_GV_URL", ""))
        parser.add_argument("--midia-ev", default="")
        parser.add_argument("--midia-gv", default="")
        parser.add_argument("--saida", required=True, help="arquivo JSON (fora do Git)")
        parser.add_argument("--midia-saida", default="",
                            help="pasta para onde copiar os PDFs (nome endereçado)")

    def handle(self, *args, **o):
        if not o["ev"] or not o["gv"]:
            raise CommandError("Informe --ev e --gv (ou LEGADO_EV_URL e LEGADO_GV_URL).")
        from gestao.identidade.models import Usuario

        from ...etapas.cadastros import LOGIN_MIGRACAO

        ev, gv = Fonte("ev", o["ev"]), Fonte("gv", o["gv"])
        ctx = Contexto(ev=ev, gv=gv, lote="correcao", relatorio=Relatorio(),
                       midia_ev=Path(o["midia_ev"]) if o["midia_ev"] else None,
                       midia_gv=Path(o["midia_gv"]) if o["midia_gv"] else None,
                       usuario_migracao=Usuario.objects.filter(
                           login__iexact=LOGIN_MIGRACAO).first())
        if ctx.usuario_migracao is None:
            raise CommandError(f'Usuário técnico "{LOGIN_MIGRACAO}" não existe no destino.')
        dados: dict = {}
        try:
            with transaction.atomic():      # só leitura: desfeita de todo modo
                dados = exportar(ctx, o["gv_oficio"])
                raise Ensaio
        except Ensaio:
            pass
        except CorrecaoRecusada as erro:
            raise CommandError(str(erro)) from erro
        finally:
            ev.fechar()
            gv.fechar()
        saida = Path(o["saida"])
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(serializar(dados), encoding="utf-8")
        alvo = dados["alvo"]
        self.stdout.write(f"exportado: ofício {dados['origem']['pk']} do GV → ofício {alvo['id']} "
                          f"do destino ({alvo['numero']:02d}/{alvo['ano']}) → {saida}")
        self.stdout.write(f"  campos: {len(dados['campos'])}; viajantes: "
                          f"{len(dados['viajantes'])}; trechos: {len(dados['trechos'])}; "
                          f"documentos: {len(dados['documentos'])}")
        self.stdout.write("  referências: " + ", ".join(
            f"{k} {len(v)}" for k, v in dados["referencias"].items()))
        for nota in dados["conferir"]:
            self.stdout.write(f"  conferir: {nota}")
        for m in dados["midia"]:
            self.stdout.write(f"  mídia: {m['destino']} ({m['tamanho']} bytes)")
        if o["midia_saida"]:
            try:
                copiados = copiar_midia(dados, Path(o["midia_saida"]))
            except CorrecaoRecusada as erro:
                raise CommandError(str(erro)) from erro
            self.stdout.write(f"  {len(copiados)} arquivo(s) copiado(s) para {o['midia_saida']}")
