"""Fluxo do ofício pelos serviços (integração com PostgreSQL, outbox e PDF)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pikepdf
import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from gestao.plataforma import outbox
from gestao.plataforma.models import EventoAuditoria, MensagemOutbox
from gestao.viagens import services
from gestao.viagens.models import Documento, Historico, Oficio, Viajante

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def cenario():
    return cenario_completo()


def test_numeracao_sequencial_reutiliza_lacuna_de_rascunho_excluido(cenario):
    op = cenario.usuarios["operador"]
    numeros = sorted(Oficio.objects.values_list("numero", flat=True))
    assert numeros == [1, 2, 3, 4, 5]
    vazio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    services.excluir_rascunho(vazio, op)
    novo = services.criar_rascunho(op)
    assert novo.numero == vazio.numero


def test_buraco_sem_exclusao_nao_e_reaproveitado(cenario):
    """D5: só a exclusão de rascunho libera número; buracos de outra origem ficam vazios."""
    op = cenario.usuarios["operador"]
    vazio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    Oficio.objects.filter(pk=vazio.pk).update(numero=20)  # ex.: dado migrado com salto
    novo = services.criar_rascunho(op)
    assert novo.numero == 21
    services.excluir_rascunho(novo, op)
    assert services.criar_rascunho(op).numero == 21  # lacuna registrada pela exclusão
    assert services.criar_rascunho(op).numero == 22


def test_data_do_oficio_fora_do_ano_do_numero_e_erro(cenario):
    """D3: número 05/2026 com data de outro ano não é aceito."""
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    with pytest.raises(services.RegraViolada, match=f"deve estar em {oficio.ano}"):
        services.salvar_dados(oficio, cenario.usuarios["operador"],
                              {"data_oficio": oficio.data_oficio.replace(year=oficio.ano + 1)})


def test_protocolo_e_obrigatorio_para_emitir(cenario):
    """D1: sem protocolo a emissão é bloqueada."""
    op = cenario.usuarios["operador"]
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    oficio = services.salvar_dados(oficio, op, {"justificativa": "Convocação de última hora."})
    prontidao = services.verificar_prontidao(oficio)
    assert [p.mensagem for p in prontidao.bloqueantes] == ["Informe o protocolo do eProtocolo."]
    with pytest.raises(services.RegraViolada, match="protocolo"):
        services.emitir(oficio, op)
    oficio = services.salvar_dados(oficio, op, {"protocolo": "123456789"})
    services.emitir(oficio, op)


def test_cancelado_mantem_numero_ocupado(cenario):
    cancelado = Oficio.objects.get(pk=cenario.ids["oficio_cancelado"])
    novo = services.criar_rascunho(cenario.usuarios["operador"])
    assert novo.numero != cancelado.numero


def test_emissao_calcula_diarias_e_publica_geracao_do_pdf(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    assert oficio.situacao == Oficio.Situacao.EMITIDO
    assert oficio.diarias_resumo == "4 x 100% + 1 x 15%"
    assert oficio.diarias_total == Decimal("2411.56")
    doc = oficio.documentos.get(tipo=Documento.Tipo.OFICIO)
    assert doc.situacao == Documento.Situacao.GERANDO
    assert MensagemOutbox.objects.filter(topico="viagens.documento.gerar").exists()


def test_worker_gera_pdf_a_2a_com_fontes_embutidas(cenario):
    while outbox.processar_lote():
        pass
    doc = Documento.objects.get(oficio_id=cenario.ids["oficio_emitido"])
    assert doc.situacao == Documento.Situacao.PRONTO and len(doc.sha256) == 64
    with doc.arquivo.open("rb") as f, pikepdf.open(f) as pdf:
        meta = pdf.open_metadata()
        assert meta.get("pdfaid:part") == "2" and meta.get("pdfaid:conformance") == "A"
        assert "/StructTreeRoot" in pdf.Root  # PDF marcado (acessível)
        for pagina in pdf.pages:
            for fonte in pagina.Resources.Font.values():
                desc = fonte.get("/FontDescriptor") or fonte.DescendantFonts[0].FontDescriptor
                assert any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        texto = b"".join(p.Contents.read_bytes() if not isinstance(p.Contents, pikepdf.Array)
                         else b"".join(c.read_bytes() for c in p.Contents) for p in pdf.pages)
        assert texto  # há conteúdo desenhado
    assert Historico.objects.filter(oficio=doc.oficio, acao=Historico.Acao.DOCUMENTO).exists()


def test_emitido_nao_pode_ser_editado(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    with pytest.raises(PermissionDenied):
        services.salvar_dados(oficio, cenario.usuarios["operador"], {"motivo": "x"})


def test_rascunho_fora_do_prazo_exige_justificativa(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_rascunho"])
    prontidao = services.verificar_prontidao(oficio)
    assert not prontidao.pode_emitir
    assert any(p.secao == "justificativa" for p in prontidao.bloqueantes)
    with pytest.raises(services.RegraViolada, match="Justificativa obrigatória"):
        services.emitir(oficio, cenario.usuarios["operador"])
    oficio = services.salvar_dados(oficio, cenario.usuarios["operador"],
                                   {"justificativa": "Convocação recebida em cima da hora.",
                                    "protocolo": "123456789"})
    services.emitir(oficio, cenario.usuarios["operador"])
    oficio.refresh_from_db()
    assert oficio.situacao == Oficio.Situacao.EMITIDO
    assert set(oficio.documentos.values_list("tipo", flat=True)) == {"oficio", "justificativa"}


def test_operador_nao_cancela_nem_reabre(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    with pytest.raises(PermissionDenied):
        services.cancelar(oficio, cenario.usuarios["operador"], "teste")
    with pytest.raises(PermissionDenied):
        services.reabrir(oficio, cenario.usuarios["operador"], "teste")


def test_gestor_reabre_e_nova_emissao_gera_versao_2(cenario):
    gestor = cenario.usuarios["gestor"]
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    services.reabrir(oficio, gestor, "Corrigir motivo.")
    oficio.refresh_from_db()
    oficio = services.salvar_dados(oficio, gestor, {"motivo": "Motivo corrigido."})
    doc = services.emitir(oficio, gestor)
    assert doc.versao == 2
    assert oficio.documentos.filter(tipo="oficio").count() == 2


def test_concorrencia_otimista(cenario):
    op = cenario.usuarios["operador"]
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    versao_antiga = oficio.versao
    services.salvar_dados(oficio, op, {"motivo": "A"}, versao=versao_antiga)
    with pytest.raises(services.ConflitoDeEdicao):
        services.salvar_dados(oficio, op, {"motivo": "B"}, versao=versao_antiga)


def test_outra_unidade_nao_ve_nem_edita(cenario):
    from gestao.viagens import policies

    op = cenario.usuarios["operador"]
    alheio = Oficio.objects.get(pk=cenario.ids["oficio_outra_unidade"])
    assert alheio not in policies.oficios_visiveis(op)
    with pytest.raises(PermissionDenied):
        services.salvar_dados(alheio, op, {"motivo": "x"})
    assert alheio in policies.oficios_visiveis(cenario.usuarios["consulta"])


def test_banco_recusa_dois_motoristas(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    with pytest.raises(IntegrityError), transaction.atomic():
        Viajante.objects.filter(oficio=oficio).update(motorista=True)


def test_trechos_fora_de_ordem_sao_recusados(cenario):
    op = cenario.usuarios["operador"]
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_vazio"])
    t = list(Oficio.objects.get(pk=cenario.ids["oficio_rascunho"]).trechos.order_by("ordem"))
    invertidos = [
        services.TrechoInformado(t[0].origem_id, t[0].destino_id, t[0].saida_em,
                                 t[0].chegada_em),
        services.TrechoInformado(t[1].origem_id, t[1].destino_id,
                                 t[0].saida_em - timedelta(days=1),
                                 t[0].chegada_em - timedelta(hours=1)),
    ]
    with pytest.raises(services.RegraViolada, match="sai antes da chegada"):
        services.salvar_trechos(oficio, op, invertidos)


def test_conflito_de_agenda_e_aviso_nao_bloqueante(cenario):
    op = cenario.usuarios["operador"]
    base = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    novo = services.criar_rascunho(op)
    novo = services.salvar_dados(novo, op, {"motivo": "Outra pauta", "viatura": base.viatura})
    services.adicionar_viajante(novo, op, base.viajantes.first().servidor)
    t = list(base.trechos.order_by("ordem"))
    services.salvar_trechos(novo, op, [services.TrechoInformado(x.origem_id, x.destino_id,
                                                                x.saida_em, x.chegada_em)
                                       for x in t])
    avisos = [p for p in services.verificar_prontidao(novo).pendencias if not p.bloqueia]
    assert any("também está no Ofício" in p.mensagem for p in avisos)


def test_trilha_de_auditoria_registra_autor_das_mudancas(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    eventos = EventoAuditoria.objects.filter(tabela="viagens_oficio", registro_id=str(oficio.pk))
    assert eventos.filter(operacao="INSERT").exists()
    assert eventos.filter(operacao="UPDATE").count() >= 3


def test_busca_por_numero_protocolo_destino_e_servidor(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    qs = Oficio.objects.all()
    assert oficio in services.buscar_por_texto(qs, f"{oficio.numero}/{oficio.ano}")
    assert oficio in services.buscar_por_texto(qs, "12.345.678-9")
    assert oficio in services.buscar_por_texto(qs, "arapongas")
    assert oficio in services.buscar_por_texto(qs, "ana beatriz")


def test_datas_de_viagem_ficam_no_fuso_local(cenario):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    primeiro = oficio.trechos.order_by("ordem").first()
    assert timezone.localtime(primeiro.saida_em).hour == 9


@pytest.mark.parametrize("formato", ["{n}", "{n:03d}", "{n:03d}/", "{n}/{a}", "{n:03d} / {a}"])
def test_busca_aceita_formatos_de_numero(cenario, formato):
    oficio = Oficio.objects.get(pk=cenario.ids["oficio_emitido"])
    termo = formato.format(n=oficio.numero, a=oficio.ano)
    assert oficio in services.buscar_por_texto(Oficio.objects.all(), termo)


class TestOrigemDoProtocolo:
    """Paridade com a referência: o número digitado é MANUAL (vale como oficial); apagar o
    número apaga a origem. Simulado/treinamento só virão da integração (fase E4)."""

    def test_digitar_marca_manual_e_apagar_limpa(self):
        c = cenario_completo()
        u = c.usuarios["operador"]
        oficio = services.criar_rascunho(u)
        assert oficio.protocolo_origem == ""
        oficio = services.salvar_dados(oficio, u, {"protocolo": "123456789"},
                                       versao=oficio.versao)
        assert oficio.protocolo_origem == Oficio.OrigemProtocolo.MANUAL
        oficio = services.salvar_dados(oficio, u, {"protocolo": ""}, versao=oficio.versao)
        assert oficio.protocolo_origem == ""
