"""Regressões do Lote H pela fronteira HTTP e pelo worker real da outbox."""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from gestao.plataforma import outbox
from gestao.plataforma.models import MensagemOutbox
from gestao.viagens import services
from gestao.viagens.models import Documento, Oficio

from .cenarios import cenario_completo
from .test_views import _post_edicao

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def c():
    return cenario_completo()


@pytest.mark.parametrize("acao", ["editar", "autosave"])
def test_salvamento_preserva_motorista_com_bloco_fechado(client, c, acao):
    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    op = c.usuarios["operador"]
    client.force_login(op)
    antes = oficio.viajantes.get(motorista=True).pk
    # Reproduz a seleção padrão REAL do navegador quando não há selected.
    html = client.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
    select = re.search(r'<select[^>]*name="motorista_externo"[^>]*>(.*?)</select>',
                       html, re.S).group(1)
    opcoes = re.findall(r'<option value="([^"]*)"([^>]*)>', select)
    selecionado = next((valor for valor, attrs in opcoes if "selected" in attrs), opcoes[0][0])
    dados = _post_edicao(oficio, tipo_transporte="viatura", viatura=oficio.viatura_id,
                         motorista_externo=selecionado)
    rota = "autosave_oficio" if acao == "autosave" else acao
    r = client.post(reverse(f"viagens:{rota}", args=[oficio.pk]), dados)
    assert r.status_code in (200, 302)
    assert oficio.viajantes.get(pk=antes).motorista


def test_falha_do_pdf_persiste_apos_rollback_do_worker(c, monkeypatch):
    def falhar(*args):
        raise RuntimeError("falha controlada do laboratório")

    monkeypatch.setattr("gestao.viagens.documentos.pdf.gerar_pdf", falhar)
    outbox.processar_lote()
    doc = Documento.objects.get(oficio_id=c.ids["oficio_emitido"])
    assert doc.situacao == Documento.Situacao.FALHOU
    assert "falha controlada" in doc.erro


def test_outro_meio_selecionado_dispensa_detalhe(c):
    from gestao.viagens.documentos.dados import dados_do_oficio

    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    oficio = services.salvar_dados(oficio, c.usuarios["operador"], {
        "tipo_transporte": "outro", "transporte_meio": "aereo", "transporte_descricao": ""})
    assert not [p for p in services.verificar_prontidao(oficio).bloqueantes
                if p.secao == "transporte"]
    assert "Aéreo" in dados_do_oficio(oficio)["transporte"]["meio"]
    assert not dados_do_oficio(oficio)["motorista"]


def test_retry_reutiliza_documento_mensagem_e_arquivo(c, monkeypatch, client):
    import hashlib

    conteudo = b"%PDF-1.7\n laboratorio sintetico"
    doc = Documento.objects.get(oficio_id=c.ids["oficio_emitido"])
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou", erro="Falha simulada")
    msg = MensagemOutbox.objects.get(chave_idempotencia=f"documento:{doc.pk}")
    MensagemOutbox.objects.filter(pk=msg.pk).update(situacao="falhou", tentativas=8)
    identidade = (doc.pk, doc.versao, doc.dados, doc.oficio.numero)
    op = c.usuarios["operador"]
    services.regenerar_documento(doc, op)
    services.regenerar_documento(doc, op)
    assert Documento.objects.filter(oficio=doc.oficio).count() == 1
    assert MensagemOutbox.objects.filter(chave_idempotencia=f"documento:{doc.pk}").count() == 1
    monkeypatch.setattr("gestao.viagens.documentos.pdf.gerar_pdf",
                        lambda *_: (conteudo, hashlib.sha256(conteudo).hexdigest()))
    outbox.processar_lote()
    doc.refresh_from_db()
    assert (doc.pk, doc.versao, doc.dados, doc.oficio.numero) == identidade
    assert doc.situacao == "pronto" and not doc.erro
    client.force_login(op)
    r = client.get(reverse("viagens:baixar_documento", args=[doc.pk]))
    assert b"".join(r.streaming_content) == conteudo
    assert r["X-Content-SHA256"] == hashlib.sha256(conteudo).hexdigest()


@pytest.mark.parametrize("perfil", ["consulta", "outra"])
def test_retry_recusa_perfil_e_unidade(client, c, perfil):
    doc = Documento.objects.get(oficio_id=c.ids["oficio_emitido"])
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou")
    client.force_login(c.usuarios[perfil])
    r = client.post(reverse("viagens:regenerar_documento", args=[doc.pk]))
    assert r.status_code in (403, 404)
    doc.refresh_from_db()
    assert doc.situacao == "falhou"


def test_data_emissao_automatica_revisao_e_snapshot(client, c):
    from datetime import timedelta

    from django.utils import timezone

    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    op = c.usuarios["operador"]
    ontem = timezone.localdate() - timedelta(days=1)
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio=ontem, data_oficio_manual=False,
                                             protocolo="123456789", justificativa="Convocação.")
    oficio.refresh_from_db()
    client.force_login(op)
    html = client.get(reverse("viagens:editar", args=[oficio.pk]), {"revisar": "1"})
    assert "A emissão usará a data de hoje" in html.content.decode()
    oficio.refresh_from_db()
    assert oficio.data_oficio == ontem  # GET da revisão não grava
    doc = services.emitir(oficio, op, versao=oficio.versao)
    oficio.refresh_from_db()
    assert oficio.data_oficio == timezone.localdate()
    assert doc.dados["data_oficio"] == timezone.localdate().strftime("%d/%m/%Y")


def test_data_emissao_recusada_nao_altera_rascunho(c):
    from datetime import timedelta

    from django.utils import timezone

    oficio = Oficio.objects.get(pk=c.ids["oficio_vazio"])
    ontem = timezone.localdate() - timedelta(days=1)
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio=ontem, data_oficio_manual=False)
    oficio.refresh_from_db()
    with pytest.raises(services.RegraViolada, match="pendências"):
        services.emitir(oficio, c.usuarios["operador"])
    oficio.refresh_from_db()
    assert oficio.data_oficio == ontem


def test_relogio_da_emissao_usa_dia_de_brasilia(c, monkeypatch):
    from datetime import UTC, datetime

    from django.utils import timezone

    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio_manual=False)
    oficio.refresh_from_db()
    instante = datetime(oficio.ano, 10, 8, 1, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: instante)
    with timezone.override("UTC"):
        data = services.preparar_data_emissao(oficio).data_oficio
        assert data.isoformat() == f"{oficio.ano}-10-07"


def test_autosave_data_incompleta_nao_torna_manual(client, c):
    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio_manual=False)
    oficio.refresh_from_db()
    client.force_login(c.usuarios["operador"])
    dados = _post_edicao(oficio, data_oficio="07/10/", data_oficio_manual="")
    r = client.post(reverse("viagens:autosave_oficio", args=[oficio.pk]), dados)
    assert r.json()["salvo"]
    oficio.refresh_from_db()
    assert not oficio.data_oficio_manual


@pytest.mark.parametrize("acao", ["editar", "autosave"])
def test_folha_preserva_data_manual_ao_alterar_outro_campo(client, c, acao):
    oficio = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    Oficio.objects.filter(pk=oficio.pk).update(data_oficio_manual=True)
    oficio.refresh_from_db()
    client.force_login(c.usuarios["operador"])
    html = client.get(reverse("viagens:editar", args=[oficio.pk])).content.decode()
    dados = _post_edicao(oficio, motivo="Descrição alterada sem trocar a data escolhida.")
    dados.pop("data_oficio_manual", None)
    # Enviar o valor que o navegador realmente serializa, incluindo um eventual
    # campo oculto. Checkbox desmarcado não entra no envio.
    for campo in re.findall(r'<input\b[^>]*name="data_oficio_manual"[^>]*>', html):
        if 'type="checkbox"' in campo and "checked" not in campo:
            continue
        valor = re.search(r'value="([^"]*)"', campo)
        dados["data_oficio_manual"] = valor.group(1) if valor else "on"
    rota = "autosave_oficio" if acao == "autosave" else acao
    resposta = client.post(reverse(f"viagens:{rota}", args=[oficio.pk]), dados)
    assert resposta.status_code in (200, 302)
    if acao == "autosave":
        assert resposta.json()["salvo"]
    data_escolhida = oficio.data_oficio
    oficio.refresh_from_db()
    assert oficio.data_oficio == data_escolhida
    assert oficio.data_oficio_manual


def test_retry_exige_tambem_permissao_de_editar(client, c):
    from django.contrib.auth.models import Permission

    usuario = c.usuarios["consulta"]
    usuario.user_permissions.add(Permission.objects.get(codename="emitir_oficio"))
    client.force_login(usuario)
    doc = Documento.objects.get(oficio_id=c.ids["oficio_emitido"])
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou")
    assert client.post(reverse("viagens:regenerar_documento", args=[doc.pk])).status_code == 403


def test_retry_concorrente_publica_uma_unica_operacao(c):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.contrib.auth import get_user_model
    from django.db import close_old_connections

    doc = Documento.objects.get(oficio_id=c.ids["oficio_emitido"])
    Documento.objects.filter(pk=doc.pk).update(situacao="falhou")
    sincronizar = Barrier(2, timeout=20)
    usuario_id = c.usuarios["operador"].pk

    def pedir():
        close_old_connections()
        try:
            usuario = get_user_model().objects.get(pk=usuario_id)
            copia = Documento.objects.select_related("oficio").get(pk=doc.pk)
            sincronizar.wait()
            return services.regenerar_documento(copia, usuario).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        pedidos = [executor.submit(pedir) for _ in range(2)]
        assert [p.result(timeout=30) for p in pedidos] == [doc.pk, doc.pk]
    assert doc.oficio.historico.filter(descricao__startswith="Nova tentativa de gerar").count() == 1
    assert MensagemOutbox.objects.get(chave_idempotencia=f"documento:{doc.pk}").tentativas == 0
