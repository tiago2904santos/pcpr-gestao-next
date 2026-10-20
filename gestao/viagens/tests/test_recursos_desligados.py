"""IA, automações e eProtocolo desligados pela configuração (ADR 0050): menus sem os módulos,
rotas em 404, botões ausentes, workers parados — e Pendências e envios manuais funcionando.
Com as chaves ligadas (padrão de DEV/TEST), tudo como antes."""

# ruff: noqa: F811
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import transaction
from django.test import Client
from django.utils import timezone

from gestao.automacao import comunicacoes, eventos, links
from gestao.automacao.models import Comunicacao, LinkAcesso
from gestao.integracoes.eprotocolo import servico as eprotocolo
from gestao.integracoes.eprotocolo.erros import Desligado
from gestao.plataforma import pendencias, rotinas
from gestao.plataforma.navegacao import navegacao_para
from gestao.viagens import envios_manuais

from .test_envios_manuais import cliente, modo, pacote_completo, urls  # noqa: F401
from .test_whatsapp_prestacao import _liberar, c  # noqa: F401

pytestmark = pytest.mark.django_db

DESLIGADOS = {"IA_HABILITADA": False, "AUTOMACAO_HABILITADA": False,
              "EPROTOCOLO_HABILITADO": False}


@pytest.fixture
def desligados(settings):
    for chave, valor in DESLIGADOS.items():
        setattr(settings, chave, valor)


def _modulos(rf, usuario) -> set[str]:
    pedido = rf.get("/")
    pedido.user = usuario
    return {m["chave"] for m in navegacao_para(pedido)["modulos"]}


def _admin(c) -> Client:
    cliente_admin = Client()
    cliente_admin.force_login(c.usuarios["admin"])
    return cliente_admin


def test_ligados_por_padrao_mostram_os_modulos(c, rf):
    assert {"automacao", "assistencia", "ajuda"} <= _modulos(rf, c.usuarios["admin"])
    assert _admin(c).get("/automacao/").status_code == 200
    assert _admin(c).get("/ajuda/").status_code == 200


def test_desligados_somem_do_menu_e_as_rotas_respondem_404(c, rf, desligados):
    assert not {"automacao", "assistencia", "ajuda"} & _modulos(rf, c.usuarios["admin"])
    assert {"viagens", "agenda"} <= _modulos(rf, c.usuarios["admin"])
    logado = _admin(c)
    for url in ("/automacao/", "/automacao/comunicacoes/", "/automacao/contatos/",
                "/automacao/excecoes/", "/assistencia/", "/assistencia/sugestoes/",
                "/ajuda/"):
        assert logado.get(url).status_code == 404, url
    anonimo = Client()
    assert anonimo.get("/api/automacao/v1/estado").status_code == 404
    assert anonimo.get("/integracoes/whatsapp/webhook/").status_code == 404
    assert anonimo.post("/integracoes/whatsapp/webhook/", data=b"{}",
                        content_type="application/json").status_code == 404
    assert anonimo.get("/automacao/").status_code == 404  # nem pede login
    assert logado.post("/eventos/solicitacoes/1/protocolo/").status_code == 404


def test_botoes_de_ia_e_eprotocolo_somem_da_folha_do_oficio(c, settings):
    url = f"/viagens/oficios/{c.ids['oficio_rascunho']}/editar/"
    logado = cliente(c)
    ligado = logado.get(url).content.decode()
    assert "Dados para o eProtocolo" in ligado
    assert 'id="ia-viagens-oficio_textos' in ligado
    settings.IA_HABILITADA = settings.EPROTOCOLO_HABILITADO = False
    desligado = logado.get(url).content.decode()
    assert "Dados para o eProtocolo" not in desligado
    assert 'id="ia-viagens-oficio_textos' not in desligado
    assert "/assistencia/" not in desligado


def test_eprotocolo_desligado_recusa_consulta(desligados):
    with pytest.raises(Desligado):
        eprotocolo.consultar("12.345.678-9")


def test_automacao_desligada_nao_agenda_nem_publica(c, settings, desligados):
    settings.N8N_EVENTOS_URL = "http://n8n.invalid/webhook/x"
    settings.N8N_EVENTOS_SEGREDO = "segredo-de-teste"
    assert not eventos.ligado()
    with transaction.atomic():
        nada = comunicacoes.agendar(tipo="viagens.diarias_liberadas", servidor_id=None,
                                    recurso="teste:1", chave="teste-desligado")
    assert nada is None
    assert not Comunicacao.objects.filter(chave="teste-desligado").exists()
    resultado = rotinas.rodar(timezone.localdate())
    assert resultado["lembretes de comprovante (WhatsApp)"] == "desligada"
    assert resultado["links de km na véspera (WhatsApp)"] == "desligada"


def test_workers_ficam_parados(desligados):
    saida = StringIO()
    call_command("processar_automacao", "--uma-vez", stdout=saida)
    call_command("processar_ia", "--uma-vez", stdout=saida)
    assert "Automações desligadas" in saida.getvalue()
    assert "Assistência por IA desligada" in saida.getvalue()


def test_pendencias_e_envio_manual_funcionam_com_tudo_desligado(c, desligados):
    ps = pacote_completo(c)
    secoes = {m.secao.slug for m in pendencias.montar(c.usuarios["admin"], timezone.localdate())}
    assert "automacao" not in secoes
    logado = cliente(c)
    assert logado.get("/agenda/pendencias/").status_code == 200
    assert "Exceções da automação" not in logado.get("/agenda/pendencias/").content.decode()
    assert envios_manuais.pendencias(c.usuarios["operador"]).filter(contexto__ps=ps.pk).exists()
    assert logado.get(f"/viagens/envios/{ps.pk}/").status_code == 200
    com, ticket, _ = envios_manuais.preparar(c.usuarios["operador"], ps.pk)
    assert "Quilometragem (KM)" in com.conteudo.texto
    # O link de KM do envio manual abre; um link de outro escopo, não.
    assert Client().get(urls(com.conteudo.texto)[0]).status_code == 200
    _, token = links.criar(escopo=LinkAcesso.Escopo.DOCUMENTOS, recurso=f"teste:{ps.pk}",
                           servidor_id=ps.servidor_id)
    assert Client().get(f"/p/{token}/").status_code == 404
    com = envios_manuais.confirmar(c.usuarios["operador"], ps.pk, ticket)
    assert com.situacao == "manual"
