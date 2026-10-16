"""Medição reproduzível da fila real, sem dados pessoais nem limiar artificial de tempo."""

import json
import os
import time
from pathlib import Path

import pytest
from django.core.management import call_command

from gestao.plataforma import outbox
from gestao.viagens import importacao
from gestao.viagens.models import ArquivoImportado, Oficio
from gestao.viagens.tests.cenarios import cenario_completo
from gestao.viagens.tests.test_importacao import pdf_textos


@pytest.mark.perf
@pytest.mark.django_db(transaction=True)
def test_lote_de_nove_pdfs_em_tres_workers(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    c = cenario_completo()
    while outbox.processar_lote():
        pass
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    for n in range(9):
        conteudo = pdf_textos(
            [
                f"DESPACHO\nOfício {oficio.numero_formatado}\n"
                f"Encaminhamento administrativo sintético número {n}, para providências."
            ]
        )
        importacao.receber(c.usuarios["operador"], f"despacho-{n}.pdf", conteudo)
    inicio = time.monotonic()
    call_command("processar_importacoes", uma_vez=True, concorrencia=3)
    segundos = round(time.monotonic() - inicio, 3)
    arquivos = ArquivoImportado.objects.all()
    assert arquivos.count() == 9
    assert arquivos.filter(estado="concluido").count() == 9
    assert all(a.partes.get().destino == f"despacho:{oficio.pk}:" for a in arquivos)
    resultado = {
        "arquivos": 9,
        "concorrencia": 3,
        "segundos": segundos,
        "corretos": 9,
        "revisoes": 0,
        "duracoes_ms": list(arquivos.values_list("duracao_ms", flat=True)),
    }
    if os.environ.get("IMPORTACAO_MEDICAO"):
        Path(os.environ["IMPORTACAO_MEDICAO"]).write_text(json.dumps(resultado), encoding="utf-8")
