"""Ofício emitido × rascunho na carga, a renumeração 127/128 e a correção pontual de um ofício já
migrado (exportar local → aplicar em produção). Só dados sintéticos."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from django.test import override_settings

from gestao.migracao.contexto import Contexto, Relatorio
from gestao.migracao.correcao import executar, exportar, serializar
from gestao.migracao.etapas.cadastros import garantir_usuario_migracao
from gestao.migracao.models import MapaLegado
from gestao.viagens.models import Documento, Historico, Oficio, Viajante

from .test_viagens_prestacao import (
    DEPOIS,
    MAIS_DEPOIS,
    FonteFalsa,
    legados,
    oficio_ev,
    oficio_gv,
    registrar,
    rodar,
)

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n% PDF sintetico da correcao\n%%EOF\n"
GERADO_EM = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
REGERADO_EM = datetime(2026, 10, 16, 14, 0, 0, 123456, tzinfo=UTC)


def _par_divergente(status_ev: str, status_gv: str, *, ev_quando=MAIS_DEPOIS,
                    gv_quando=DEPOIS) -> tuple[dict, dict]:
    """O mesmo ofício nos dois sistemas, editado nos dois depois da carga, com equipes
    diferentes (EV: um servidor; GV: dois)."""
    gv_linha = oficio_gv(5, 126, motivo="Motivo do GV", atualizado=gv_quando, status=status_gv)
    ev, gv = legados(
        {"viagens_oficios_oficio": [oficio_ev(1, 126, motivo="Motivo do EV",
                                              atualizado=ev_quando, protocolo="987654321",
                                              legado="gerenciador_viagens", status=status_ev)],
         "viagens_oficios_oficio_servidores": [{"id": 1, "oficio_id": 1, "servidor_id": 1}]},
        {"oficios_oficio": [gv_linha],
         "oficios_oficio_servidores": [{"id": 1, "oficio_id": 5, "servidor_id": 71},
                                       {"id": 2, "oficio_id": 5, "servidor_id": 72}]})
    registrar(ev, "oficios_oficio", gv_linha, 1, mudou=True)
    return ev, gv


# ---------------------------------------------------------------------------- regra da etapa
def test_emitido_no_gv_vence_rascunho_do_ev_editado_depois(base):
    ev, gv = _par_divergente("RASCUNHO", "FINALIZADO")

    relatorio = rodar(ev, gv)

    oficio = Oficio.objects.get()
    assert oficio.motivo == "Motivo do GV"
    assert oficio.situacao == "emitido"
    assert set(Viajante.objects.filter(oficio=oficio).values_list("servidor_id", flat=True)) \
        == {base["s1"].pk, base["s2"].pk}
    assert relatorio.contagens["oficio"]["emitido_vence_rascunho"] == 1
    assert "editado_nos_dois" not in relatorio.contagens["oficio"]
    [item] = [c for c in relatorio.conferir if "emitido no GV" in c["motivo"]]
    assert (item["ev_pk"], item["gv_pk"]) == (1, 5)
    assert "motivo" in item["campos"] and "situacao" in item["campos"]


def test_emitido_no_ev_vence_rascunho_do_gv_editado_depois(base):
    ev, gv = _par_divergente("GERADO", "RASCUNHO", ev_quando=DEPOIS, gv_quando=MAIS_DEPOIS)

    relatorio = rodar(ev, gv)

    oficio = Oficio.objects.get()
    assert (oficio.motivo, oficio.situacao) == ("Motivo do EV", "emitido")
    assert relatorio.contagens["oficio"]["emitido_vence_rascunho"] == 1
    assert any("emitido no EV" in c["motivo"] for c in relatorio.conferir)


def test_dois_rascunhos_continua_valendo_a_edicao_mais_recente(base):
    ev, gv = _par_divergente("RASCUNHO", "RASCUNHO")

    relatorio = rodar(ev, gv)

    assert Oficio.objects.get().motivo == "Motivo do EV"
    assert relatorio.contagens["oficio"]["editado_nos_dois"] == 1
    assert "emitido_vence_rascunho" not in relatorio.contagens["oficio"]


def test_rascunho_do_ev_cede_o_numero_ao_oficio_emitido_so_no_gv(base):
    ev, gv = legados(
        {"viagens_oficios_oficio": [oficio_ev(1, 127, status="RASCUNHO"),
                                    oficio_ev(2, 128, status="RASCUNHO"),
                                    oficio_ev(3, 141)]},
        {"oficios_oficio": [oficio_gv(9, 127, status="GERADO"),
                            oficio_gv(10, 128, status="RASCUNHO")]})

    relatorio = rodar(ev, gv)

    gv_127 = Oficio.objects.get(pk=MapaLegado.objects.get(
        sistema="gv", tabela="oficios_oficio", origem_pk="9").destino_pk)
    ev_127 = Oficio.objects.get(pk=MapaLegado.objects.get(
        sistema="ev", tabela="viagens_oficios_oficio", origem_pk="1").destino_pk)
    gv_128 = Oficio.objects.get(pk=MapaLegado.objects.get(
        sistema="gv", tabela="oficios_oficio", origem_pk="10").destino_pk)
    # O emitido do GV fica com o número do PDF; o rascunho do EV é o renumerado.
    assert (gv_127.numero, gv_127.situacao) == (127, "emitido")
    assert (ev_127.numero, ev_127.situacao) == (142, "rascunho")
    historico = Historico.objects.get(oficio=ev_127)
    assert historico.dados["numero_anterior"] == 127
    assert "emitido no Gerenciador de Viagens" in historico.descricao
    # Rascunho × rascunho: segue a regra antiga (quem entra depois, o do GV, é renumerado).
    assert gv_128.numero == 143
    assert Oficio.objects.get(numero=128).pk != gv_128.pk
    assert relatorio.contagens["oficio"]["renumerado"] == 2
    assert any("emitido só no GV" in c["motivo"] for c in relatorio.conferir)


# ---------------------------------------------------------------------------- correção pontual
@pytest.fixture
def ja_migrado_errado(base, tmp_path):
    """Estado da produção: a carga antiga deixou valer o rascunho do EV. Aqui os dois lados
    eram rascunho na hora da carga; depois o GV aparece finalizado, com o PDF regerado."""
    ev, gv = _par_divergente("RASCUNHO", "RASCUNHO")
    rodar(ev, gv)
    oficio = Oficio.objects.get()
    assert (oficio.situacao, oficio.motivo) == ("rascunho", "Motivo do EV")
    gv["oficios_oficio"][0]["status"] = "FINALIZADO"
    midia_gv = tmp_path / "gv"
    for nome, conteudo in (("antigo.pdf", PDF + b"v1"), ("novo.pdf", PDF)):
        p = midia_gv / "documentos" / "gerados" / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(conteudo)
    gv["documentos_documentoartefato"] = [
        {"id": "a1", "tipo": "oficio", "formato": "pdf", "oficio_id": 5, "criado_em": GERADO_EM,
         "arquivo": "documentos/gerados/antigo.pdf", "hash_sha256": "", "payload_snapshot": {}},
        {"id": "a2", "tipo": "oficio", "formato": "pdf", "oficio_id": 5,
         "criado_em": REGERADO_EM, "arquivo": "documentos/gerados/novo.pdf",
         "hash_sha256": hashlib.sha256(PDF).hexdigest(), "payload_snapshot": {}}]
    ctx = Contexto(ev=FonteFalsa(ev), gv=FonteFalsa(gv), lote="correcao", relatorio=Relatorio(),
                   midia_gv=midia_gv)
    garantir_usuario_migracao(ctx)
    dados = json.loads(serializar(exportar(ctx, 5)))     # ida e volta pelo arquivo
    media = tmp_path / "media"
    destino = media / dados["midia"][0]["destino"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(PDF)
    with override_settings(MEDIA_ROOT=str(media)):
        yield oficio, dados


def test_exportacao_traz_o_agregado_do_gv_e_o_pdf_mais_recente(ja_migrado_errado, base):
    oficio, dados = ja_migrado_errado
    assert dados["alvo"]["id"] == oficio.pk
    assert dados["campos"]["situacao"] == "emitido"
    assert dados["campos"]["motivo"] == "Motivo do GV"
    assert {v["servidor_id"] for v in dados["viajantes"]} == {base["s1"].pk, base["s2"].pk}
    [doc] = dados["documentos"]
    sha = hashlib.sha256(PDF).hexdigest()
    assert doc["origem"] == ["gv", "documentos_documentoartefato", "a2"]
    assert doc["campos"]["arquivo"] == f"legado/gv/{sha[:2]}/{sha}.pdf"
    assert dados["midia"] == [{"sistema": "gv", "origem": "documentos/gerados/novo.pdf",
                               "raiz": dados["midia"][0]["raiz"], "destino":
                               f"legado/gv/{sha[:2]}/{sha}.pdf", "sha256": sha,
                               "tamanho": len(PDF)}]
    assert sorted(dados["referencias"]["cadastros.Servidor"]) == sorted(
        [base["s1"].pk, base["s2"].pk])


def test_ensaio_nao_grava_e_gravar_aplica_uma_vez_so(ja_migrado_errado, base):
    oficio, dados = ja_migrado_errado

    plano, _ = executar(dados, gravar=False)

    assert not plano.problemas
    assert {"motivo", "situacao", "emitido_em"} <= set(plano.mudam)
    assert plano.filhos_mudam == ["viajantes"]
    oficio.refresh_from_db()
    assert (oficio.situacao, oficio.versao) == ("rascunho", 1)
    assert not Documento.objects.exists()

    plano, docs = executar(dados, gravar=True)

    oficio.refresh_from_db()
    assert (oficio.situacao, oficio.motivo, oficio.versao) == ("emitido", "Motivo do GV", 2)
    assert oficio.emitido_em == GERADO_EM          # primeiro PDF gerado, como na etapa
    assert list(oficio.viajantes.values_list("servidor_id", "motorista")) == [
        (base["s1"].pk, True), (base["s2"].pk, False)]
    [doc] = Documento.objects.filter(pk__in=docs)
    assert (doc.tipo, doc.versao, doc.situacao) == ("oficio", 1, "pronto")
    assert doc.sha256 == hashlib.sha256(PDF).hexdigest()
    assert doc.emitido_em == REGERADO_EM
    with doc.arquivo.open("rb") as f:
        assert f.read() == PDF
    historico = Historico.objects.get(oficio=oficio, acao="alterado")
    assert historico.descricao.startswith("Corrigido para a versão emitida no Gerenciador")
    assert "finalizada em 25/09/2026" in historico.descricao
    assert historico.dados["correcao"] == dados["chave"]
    assert historico.usuario.login == "migracao"
    mapa = dict(MapaLegado.objects.filter(destino_pk=str(oficio.pk), modelo="viagens.Oficio")
                .values_list("sistema", "criado"))
    assert mapa == {"gv": True, "ev": False}
    assert MapaLegado.objects.get(sistema="gv", origem_pk="a2").destino_pk == str(doc.pk)

    contagem = (Documento.objects.count(), Historico.objects.count(), Viajante.objects.count(),
                MapaLegado.objects.count())
    plano, docs = executar(dados, gravar=True)

    assert plano.ja_aplicada and docs == []
    oficio.refresh_from_db()
    assert oficio.versao == 2
    assert contagem == (Documento.objects.count(), Historico.objects.count(),
                        Viajante.objects.count(), MapaLegado.objects.count())


def test_recusa_se_o_alvo_mudou_depois_da_exportacao(ja_migrado_errado):
    oficio, dados = ja_migrado_errado
    Oficio.objects.filter(pk=oficio.pk).update(versao=3)

    plano, docs = executar(dados, gravar=True)

    assert any("versao" in p for p in plano.problemas)
    assert docs == []
    oficio.refresh_from_db()
    assert oficio.situacao == "rascunho"
    assert not Historico.objects.filter(acao="alterado").exists()


def test_recusa_sem_o_pdf_no_media_root(ja_migrado_errado, tmp_path):
    oficio, dados = ja_migrado_errado
    with override_settings(MEDIA_ROOT=str(tmp_path / "vazio")):
        plano, _ = executar(dados, gravar=True)

    assert any("ausente no MEDIA_ROOT" in p for p in plano.problemas)
    oficio.refresh_from_db()
    assert oficio.situacao == "rascunho"
