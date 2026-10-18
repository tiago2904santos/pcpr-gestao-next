"""Fila manual, isolamento dos links, confirmação explícita e bloqueio dos transportes."""

# ruff: noqa: F811
import io
import re
import zipfile
from datetime import timedelta
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest
from django.core.files.base import ContentFile
from django.test import Client, override_settings
from django.utils import timezone

from gestao.automacao import entrega
from gestao.automacao.models import Comunicacao, LinkAcesso, TentativaEntrega
from gestao.plataforma.models import Notificacao
from gestao.viagens import diario, envios_manuais, km_link
from gestao.viagens.models import Documento, PrestacaoServidor, RelatorioTecnico

from .test_whatsapp_prestacao import Espiao, _liberar, c  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def modo(settings):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    settings.URL_PUBLICA = "https://sistema.example.test"


def pdf_teste():
    import pikepdf
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


def pacote_completo(c):
    p = c.ps.prestacao
    doc = Documento.objects.filter(oficio=p.oficio, tipo="oficio").latest("versao")
    doc.situacao = "pronto"
    doc.sha256 = "a" * 64
    doc.arquivo.save("oficio-teste.pdf", ContentFile(pdf_teste()), save=False)
    doc.save()
    RelatorioTecnico.objects.update_or_create(prestacao=p, defaults={
        "motivo": "Visita técnica fictícia", "atividade": "Inspeção de teste",
        "conclusao": "Atividade concluída no laboratório"})
    d = diario.obter(p)
    pessoa = km_link.responsavel(d)
    ps = PrestacaoServidor.objects.select_related("servidor", "prestacao__oficio").get(
        prestacao=p, servidor=pessoa)
    ps.servidor.telefone = "41999997771"
    ps.servidor.save(update_fields=["telefone"])
    c.ps = ps
    _liberar(c)
    return ps


def cliente(c):
    client = Client()
    client.force_login(c.usuarios["operador"])
    return client


def urls(texto):
    return [urlparse(url).path for url in re.findall(r"https://\S+", texto)]


def test_liberacao_gera_pendencia_unica_e_notificacao_sem_enviar(c, monkeypatch):
    publicar = Mock()
    monkeypatch.setattr("gestao.automacao.eventos.publicar", publicar)
    _liberar(c)
    c.ps.refresh_from_db()
    c1 = envios_manuais.enfileirar(c.ps, c.usuarios["operador"])
    c2 = envios_manuais.enfileirar(c.ps, c.usuarios["operador"])
    assert c1.pk == c2.pk
    assert c1.contexto["ps"] == c.ps.pk and c1.contexto["manual"] is True
    assert c1.situacao == "aguardando_aprovacao"
    assert Notificacao.objects.filter(link=f"/viagens/envios/{c.ps.pk}/").exists()
    assert envios_manuais.pendencias(c.usuarios["operador"]).filter(pk=c1.pk).exists()
    assert entrega.reservar() is None
    assert not TentativaEntrega.objects.exists()
    publicar.assert_not_called()  # nenhum disparo de envio para o n8n


def test_prepara_mensagem_com_todos_itens_sem_marcar_envio(c, monkeypatch):
    ps = pacote_completo(c)
    com, ticket, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    texto = com.conteudo.texto
    assert all(s in texto for s in ("Saque das diárias", "Ofício:", "Relatório técnico (RT)",
                                    "Quilometragem (KM)", ps.servidor.nome))
    assert len(urls(texto)) == 1
    assert not LinkAcesso.objects.filter(escopo="documentos").exists()
    assert com.situacao == "aguardando_aprovacao" and com.enviada_em is None
    assert "rt" in com.conteudo.parametros[0]
    assert com.conteudo.parametros[0]["rt"]["nome"] == ps.servidor.nome
    monkeypatch.setattr("gestao.viagens.relatorio.pdf_do_documento", lambda dados: pdf_teste())
    conteudo, nome, mime = envios_manuais.arquivos(c.usuarios["operador"], ps.pk, com.pk, "zip")
    assert mime == "application/zip" and nome.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
        assert pacote.namelist() == ["oficio.pdf", "relatorio-tecnico.pdf"]
    conteudo, _, mime = envios_manuais.arquivos(c.usuarios["operador"], ps.pk, com.pk, "unico")
    import pikepdf
    with pikepdf.open(io.BytesIO(conteudo)) as pdf:
        assert len(pdf.pages) == 2
    assert mime == "application/pdf"
    resposta = cliente(c).get(f"/viagens/envios/{ps.pk}/arquivos/{com.pk}/zip/")
    assert resposta.status_code == 200
    assert resposta["Content-Disposition"].startswith("attachment;")
    com = envios_manuais.confirmar(c.usuarios["operador"], ps.pk, ticket)
    assert com.situacao == "manual" and com.enviada_em and com.aprovada_por_id
    assert com.entrega == ""  # declaração humana não é confirmação de entrega
    assert envios_manuais.confirmar(c.usuarios["operador"], ps.pk, ticket).pk == com.pk
    assert not TentativaEntrega.objects.exists()


def test_outro_integrante_nao_recebe_km_e_cada_rt_e_individual(c):
    motorista = pacote_completo(c)
    outro = (envios_manuais.elegiveis().filter(prestacao=motorista.prestacao)
             .exclude(pk=motorista.pk).first())
    outro.servidor.telefone = "41999997772"
    outro.servidor.save(update_fields=["telefone"])
    com, _, _ = envios_manuais.preparar(c.usuarios["operador"], outro.pk)
    assert "Quilometragem (KM)" not in com.conteudo.texto
    assert com.conteudo.parametros[0]["rt"]["nome"] == outro.servidor.nome


@pytest.mark.parametrize("mudanca", ["telefone", "rt", "liberacao"])
def test_mudanca_recusa_confirmacao_e_download_do_pacote_anterior(c, mudanca):
    ps = pacote_completo(c)
    com, ticket, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    if mudanca == "telefone":
        ps.servidor.telefone = "41999998888"
        ps.servidor.save(update_fields=["telefone"])
    elif mudanca == "rt":
        RelatorioTecnico.objects.filter(prestacao=ps.prestacao).update(conclusao="Texto corrigido")
    else:
        PrestacaoServidor.objects.filter(pk=ps.pk).update(
            prazo_limite_saque=timezone.localdate() + timedelta(days=10))
    with pytest.raises(ValueError, match="dados mudaram"):
        envios_manuais.confirmar(c.usuarios["operador"], ps.pk, ticket)
    with pytest.raises(ValueError, match="dados mudaram"):
        envios_manuais.arquivos(c.usuarios["operador"], ps.pk, com.pk, "zip")
    nova = envios_manuais.enfileirar(ps, c.usuarios["operador"])
    com.refresh_from_db()
    assert nova.pk != com.pk and com.situacao == "obsoleta"


def test_reserva_n8n_e_worker_recusam_inclusive_apos_trocar_transporte(c):
    ps = pacote_completo(c)
    com, _, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    for transporte in ("manual", "interno", "n8n"):
        with override_settings(AUTOMACAO_TRANSPORTE=transporte):
            resultado = entrega.reservar_pela_api(com.pk, versao_esperada=com.revisao,
                                                  execucao="teste-manual")
            assert resultado.reserva is None and resultado.recusa == "regra_violada"
    with override_settings(AUTOMACAO_TRANSPORTE="manual"), pytest.raises(RuntimeError):
        entrega.enviar(entrega.Reserva(0, 0, None), porta=Espiao())
    assert not TentativaEntrega.objects.exists()


def test_get_nao_gera_link_preparar_nao_confirma_e_confirmacao_exige_declaracao(c):
    ps = pacote_completo(c)
    op = cliente(c)
    url = f"/viagens/envios/{ps.pk}/"
    n = LinkAcesso.objects.count()
    assert op.get(url).status_code == 200
    assert LinkAcesso.objects.count() == n
    resposta = op.post(url, {"acao": "preparar"})
    assert resposta.status_code == 200
    ticket = resposta.context["ticket"]
    com = Comunicacao.objects.get(contexto__ps=ps.pk, contexto__manual=True,
                                   situacao="aguardando_aprovacao")
    assert op.get(url).context["ticket"] == ticket  # voltar do WhatsApp mantém a conferência
    op.post(url, {"acao": "confirmar", "ticket": ticket})
    com.refresh_from_db()
    assert com.situacao == "aguardando_aprovacao"
    op.post(url, {"acao": "confirmar", "ticket": ticket, "confirmo": "sim"})
    com.refresh_from_db()
    assert com.situacao == "manual"


def test_link_km_revogado_e_download_anonimo_nao_abrem(c):
    ps = pacote_completo(c)
    com, _, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    url = urls(com.conteudo.texto)[0]
    link = LinkAcesso.objects.get(comunicacao=com, escopo="km")
    LinkAcesso.objects.filter(pk=link.pk).update(revogado_em=timezone.now())
    assert Client().get(url).status_code == 404
    assert Client().get(f"/viagens/envios/{ps.pk}/arquivos/{com.pk}/zip/").status_code == 302



def test_operador_outra_unidade_e_visitante_nao_acessam(c):
    ps = pacote_completo(c)
    url = f"/viagens/envios/{ps.pk}/"
    anonimo = Client()
    assert anonimo.get(url).status_code == 302
    op = cliente(c)
    outra = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=c.ids["oficio_outra_unidade"]).first()
    if outra:
        assert op.get(f"/viagens/envios/{outra.pk}/").status_code == 404
    with pytest.raises(ValueError):
        envios_manuais.confirmar(c.usuarios["operador"], ps.pk, "ticket-falso")


def test_outro_operador_e_pacote_de_outra_pessoa_nao_autorizam_download(c):
    ps = pacote_completo(c)
    com, _, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    op_outra_unidade = Client()
    op_outra_unidade.force_login(c.usuarios["outra"])
    assert op_outra_unidade.get(f"/viagens/envios/{ps.pk}/").status_code == 404
    assert op_outra_unidade.get(
        f"/viagens/envios/{ps.pk}/arquivos/{com.pk}/zip/").status_code == 404
    outra_ps = (envios_manuais.elegiveis().filter(prestacao=ps.prestacao)
                .exclude(pk=ps.pk).first())
    with pytest.raises(ValueError, match="dados mudaram"):
        envios_manuais.arquivos(c.usuarios["operador"], outra_ps.pk, com.pk, "zip")


def test_notificacao_nao_duplica_ao_atualizar_e_e_resolvida_ao_confirmar(c):
    ps = pacote_completo(c)
    op = c.usuarios["operador"]
    destino = f"/viagens/envios/{ps.pk}/"
    envios_manuais.enfileirar(ps, op)
    RelatorioTecnico.objects.filter(prestacao=ps.prestacao).update(conclusao="Revisão de teste")
    envios_manuais.enfileirar(ps, op)
    assert Notificacao.objects.filter(link=destino, usuario=op, lida=False).count() == 1
    com, ticket, _ = envios_manuais.preparar(op, ps.pk)
    envios_manuais.confirmar(op, ps.pk, ticket)
    assert not Notificacao.objects.filter(link=destino, lida=False).exists()
    historico = cliente(c).get(f"/viagens/envios/{ps.pk}/?envio={com.pk}")
    assert historico.status_code == 200 and historico.context["confirmado"]
    assert not historico.context["ticket"]
    assert historico.context["arquivos_atuais"]


def test_atualizar_e_idempotente_e_pacote_novo_nao_reenvia_historico(c):
    ps = pacote_completo(c)
    op = c.usuarios["operador"]
    envios_manuais.sincronizar(op)
    assert envios_manuais.sincronizar(op) == 0
    com, ticket, _ = envios_manuais.preparar(op, ps.pk)
    envios_manuais.confirmar(op, ps.pk, ticket)
    assert envios_manuais.enfileirar(ps, op).pk == com.pk
    assert cliente(c).get("/viagens/envios/?aba=historico").status_code == 200


@pytest.mark.parametrize("confirmado", [False, True])
def test_desfazer_correcao_restaura_pendencia_sem_reenviar_conteudo_confirmado(c, confirmado):
    ps = pacote_completo(c)
    op = c.usuarios["operador"]
    com, ticket, _ = envios_manuais.preparar(op, ps.pk)
    if confirmado:
        envios_manuais.confirmar(op, ps.pk, ticket)
    rt = RelatorioTecnico.objects.get(prestacao=ps.prestacao)
    original = rt.conclusao
    rt.conclusao = "Correção temporária de teste"
    rt.save()
    nova = envios_manuais.enfileirar(ps, op)
    rt.conclusao = original
    rt.save()
    restaurada = envios_manuais.enfileirar(ps, op)
    nova.refresh_from_db()
    assert restaurada.pk == com.pk and nova.situacao == "obsoleta"
    assert restaurada.situacao == ("manual" if confirmado else "aguardando_aprovacao")
    if not confirmado:
        with pytest.raises(ValueError):
            envios_manuais.confirmar(op, ps.pk, ticket)
