"""Garantias da automação que a revisão cética pediu para provar: ações das telas (POST),
aprovação por outra pessoa e com a automação ligada, idempotência sob concorrência e depois
de religar, recebimento V1 com vários anexos, eventos para o n8n, manutenção (validade,
órfãos, retenção), limite por hora, lembretes encerrados pelo caminho do WhatsApp, a
prestação certa entre duas abertas, arquivo grande e repetido, e o webhook (413 e corpo
re-serializado)."""

# ruff: noqa: F811  (a fixture `c` vem do módulo vizinho)
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone

from gestao.automacao import (
    chaves,
    entrega,
    eventos,
    ferramentas,
    manutencao,
    recebimentos,
    simulador,
)
from gestao.automacao.api import credenciais
from gestao.automacao.models import (
    Comunicacao,
    ExcecaoAutomacao,
    LinkAcesso,
    Recebimento,
    StatusEntrega,
)
from gestao.automacao.models_api import EventoIntegracao, PedidoAprovacao
from gestao.integracoes.whatsapp import webhook
from gestao.viagens import comunicacoes as viagens_whatsapp
from gestao.viagens.models import AnexoPrestacao, PrestacaoServidor

from .test_whatsapp_prestacao import (  # noqa: F401  (fixtures e utilitários)
    E164,
    PDF,
    TODOS,
    Espiao,
    _aviso,
    _contato_ativo,
    _liberar,
    _ligar,
    _processar_entradas,
    _sem_trava_de_transacao,
    c,
)

pytestmark = pytest.mark.django_db
S = Comunicacao.Situacao


def _cliente(usuario) -> Client:
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


# ------------------------------------------------------------------ ações das telas
def test_acoes_da_comunicacao_pela_tela(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    op = _cliente(c.usuarios["operador"])
    url = f"/automacao/comunicacoes/{aviso.pk}"
    op.post(f"{url}/simular_falha/", {"resultado": "incerta"})
    entrega.processar_uma(porta=Espiao())
    aviso.refresh_from_db()
    assert aviso.situacao == S.INCERTA
    op.post(f"{url}/tentar/")  # sem a declaração: recusado
    aviso.refresh_from_db()
    assert aviso.situacao == S.INCERTA
    op.post(f"{url}/tentar/", {"nao_chegou": "sim"})
    aviso.refresh_from_db()
    assert aviso.situacao == S.AGENDADA and aviso.revisao == 2
    assert not ExcecaoAutomacao.objects.filter(comunicacao=aviso, situacao="aberta").exists()
    op.post(f"{url}/manual/")
    aviso.refresh_from_db()
    assert aviso.situacao == S.MANUAL
    # Outra unidade não age (404).
    assert _cliente(c.usuarios["outra"]).post(f"{url}/cancelar/").status_code == 404


def test_excecao_assumir_resolver_e_descartar_pela_tela(c):
    _ligar(c, *TODOS)
    _contato_ativo(c, testador=False)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    e = ExcecaoAutomacao.objects.get(tipo="contato")
    op = _cliente(c.usuarios["operador"])
    op.post(f"/automacao/excecoes/{e.pk}/assumir/")
    e.refresh_from_db()
    assert e.responsavel == c.usuarios["operador"]
    op.post(f"/automacao/excecoes/{e.pk}/resolver/", {"resolucao": ""})  # sem texto: não
    e.refresh_from_db()
    assert e.situacao == "aberta"
    op.post(f"/automacao/excecoes/{e.pk}/resolver/", {"resolucao": "Avisei por telefone."})
    e.refresh_from_db()
    assert e.situacao == "resolvida" and e.resolvida_por == c.usuarios["operador"]
    assert _cliente(c.usuarios["outra"]).get(f"/automacao/excecoes/{e.pk}/").status_code == 404


def test_chaves_contato_testador_e_links_pela_tela(c):
    admin = _cliente(c.usuarios["admin"])
    admin.post("/automacao/canal/chave/", {"nome": "geral", "estado": "ligada"})
    assert chaves.geral_ligada()
    admin.post("/automacao/canal/desligar/", {"motivo": "teste"})
    assert not chaves.geral_ligada()
    contato = _contato_ativo(c)
    op = _cliente(c.usuarios["operador"])
    op.post(f"/automacao/contatos/{contato.pk}/revogar/", {"motivo": "Saiu do teste"})
    contato.refresh_from_db()
    assert contato.revogado_em is not None
    from gestao.automacao.models import DestinatarioAutorizado, EventoContato
    d = DestinatarioAutorizado.objects.get()
    admin.post(f"/automacao/testadores/{d.pk}/remover/")
    d.refresh_from_db()
    assert d.removido_em is not None
    # O histórico dos contatos fica auditado sem o número.
    acoes = set(EventoContato.objects.values_list("acao", flat=True))
    assert {"cadastrado", "verificado", "optin", "revogado", "testador_incluido",
            "testador_removido"} <= acoes
    assert EventoContato.objects.filter(acao="cadastrado").get().final == E164[-4:]


def test_link_pessoal_revogacao_respeita_a_unidade(c):
    from gestao.automacao import links

    link, _ = links.criar(escopo="km", recurso="viagens.diario:1",
                          servidor_id=c.ps.servidor_id)
    outra = _cliente(c.usuarios["outra"])
    if c.ps.servidor.unidade_id:  # servidor de outra unidade: 404
        assert outra.post(f"/automacao/links/{link.pk}/revogar/").status_code == 404
    _cliente(c.usuarios["operador"]).post(f"/automacao/links/{link.pk}/revogar/")
    assert LinkAcesso.objects.get(pk=link.pk).revogado_em is not None


def test_arquivo_recebido_so_para_a_unidade(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    simulador.simular_resposta(c.usuarios["operador"], _aviso(c).pk, conteudo=PDF,
                               nome="c.pdf")
    _processar_entradas()
    recebimentos.processar_um()
    r = Recebimento.objects.get()
    url = f"/automacao/recebidos/{r.pk}/arquivo/"
    assert _cliente(c.usuarios["operador"]).get(url).status_code == 200
    assert _cliente(c.usuarios["outra"]).get(url).status_code == 404


# ------------------------------------------------------------------ aprovação
def test_quem_pede_nao_aprova_e_desligada_nao_aprova(c):
    _ligar(c, *TODOS, "ferramentas")
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    gestor = c.usuarios["gestor"]
    r = ferramentas.executar("comunicacoes.cancelar", {"comunicacao": aviso.pk},
                             usuario=gestor, origem="tela")
    pedido = r.aprovacao
    from django.core.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        ferramentas.aprovar(gestor, pedido.pk)
    chaves.desligar_tudo(c.usuarios["admin"], "incidente")
    with pytest.raises(ferramentas.FerramentaRecusada):
        ferramentas.aprovar(c.usuarios["operador"], pedido.pk)
    chaves.alterar(c.usuarios["admin"], chaves.GERAL, estado="ligada")
    ferramentas.aprovar(c.usuarios["operador"], pedido.pk)
    pedido.refresh_from_db()
    aviso.refresh_from_db()
    assert pedido.situacao == PedidoAprovacao.Situacao.APROVADO
    assert pedido.decidido_por == c.usuarios["operador"] and aviso.situacao == S.CANCELADA


def test_negacao_de_ferramenta_fica_registrada(c):
    from django.core.exceptions import PermissionDenied

    from gestao.automacao.models_api import ExecucaoFerramenta

    with pytest.raises(PermissionDenied):
        ferramentas.executar("prestacao.situacao", {"ps": c.ps.pk},
                             usuario=c.usuarios["outra"])
    assert ExecucaoFerramenta.objects.filter(resultado="negada",
                                             usuario=c.usuarios["outra"]).exists()


# ------------------------------------------------------------------ idempotência
@pytest.fixture
def n8n(c, settings):
    settings.AUTOMACAO_TRANSPORTE = "n8n"
    settings.WHATSAPP = {"modelos": "viagens.diarias_liberadas=diarias_teste:pt_BR"}
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    _, token = credenciais.emitir(c.usuarios["admin"], nome="n8n", tipo="transporte")
    return token


def _post(token, caminho, corpo, chave):
    return Client().post(f"/api/automacao/v1{caminho}", json.dumps(corpo),
                         content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}",
                         HTTP_IDEMPOTENCY_KEY=chave)


def test_423_nao_e_guardado_e_depois_de_religar_a_mesma_chave_funciona(c, n8n):
    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-religar"
    chaves.desligar_tudo(c.usuarios["admin"], "teste")
    assert _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).status_code == 423
    chaves.alterar(c.usuarios["admin"], chaves.GERAL, estado="ligada")
    assert _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).status_code == 200


def test_chave_em_andamento_nao_executa_duas_vezes(c, n8n):
    from gestao.automacao.models_api import CredencialIntegracao, RegistroIdempotencia

    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-concorrente"
    cred = CredencialIntegracao.objects.get(nome="n8n")
    # A primeira chamada "ainda executando": o registro em andamento já existe.
    RegistroIdempotencia.objects.create(credencial=cred, chave=chave,
                                        rota=f"/api/automacao/v1/comunicacoes/{aviso.pk}/reservar",
                                        impressao="x", status=0, corpo={})
    r = _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave)
    assert r.status_code in (409, 422)
    aviso.refresh_from_db()
    assert aviso.situacao == S.AGENDADA  # a segunda não reservou


def test_repeticao_aceita_o_token_da_primeira_reserva(c, n8n):
    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-repete"
    primeira = _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).json()
    _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave)  # a repetição
    r = _post(n8n, f"/comunicacoes/{aviso.pk}/resultado",
              {"reserva_token": primeira["reserva"]["token"], "resultado": "enviada",
               "provedor_mensagem_id": "wamid.REP1"}, f"resultado:{aviso.pk}:repete-1")
    assert r.status_code == 200 and r.json()["estado"] == "enviada"


def test_recebimento_v1_com_dois_anexos_e_sem_associacao_automatica(c, n8n):
    from gestao.automacao.models_api import CredencialIntegracao

    cred = CredencialIntegracao.objects.get(nome="n8n")
    cred.escopos = [*cred.escopos, "recebimentos:criar"]
    cred.save(update_fields=["escopos"])
    for indice, conteudo in enumerate((PDF, PDF + b"%%outro")):
        r = Client().post("/api/automacao/v1/recebimentos", {
            "arquivo": _arquivo(conteudo), "canal": "whatsapp", "mensagem_id_canal": "wamid.V1",
            "anexo_indice": str(indice), "total_anexos": "2", "remetente": E164,
            "recebido_em": timezone.now().isoformat(),
            "sha256": hashlib.sha256(conteudo).hexdigest()},
            HTTP_AUTHORIZATION=f"Bearer {n8n}",
            HTTP_IDEMPOTENCY_KEY=f"receb:whatsapp:wamid.V1:{indice}")
        assert r.status_code == 202, r.content
    assert Recebimento.objects.filter(mensagem_id="wamid.V1").count() == 2
    # Sem a assinatura do provedor, nada entra sozinho na prestação.
    assert not AnexoPrestacao.objects.filter(servidor=c.ps, tipo="comprovante").exists()
    assert ExcecaoAutomacao.objects.filter(tipo="associacao").count() == 2


def _arquivo(conteudo):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("comprovante.pdf", conteudo, content_type="application/pdf")


# ------------------------------------------------------------------ eventos e manutenção
@override_settings(N8N_EVENTOS_URL="http://n8n.invalid/webhook/pcpr-eventos",
                   N8N_EVENTOS_SEGREDO="segredo-de-teste")
def test_eventos_assinados_entregues_com_repeticao(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    EventoIntegracao.objects.exclude(tipo="comunicacao.agendada").delete()  # os das chaves
    e = EventoIntegracao.objects.get(tipo="comunicacao.agendada")
    assert e.corpo["recurso"]["tipo"] == "comunicacao" and "destino" not in json.dumps(e.corpo)
    chamadas = []

    def falha(url, corpo, cab):
        chamadas.append(cab)
        return 503

    assert eventos.processar_um(postar=falha)
    e.refresh_from_db()
    assert e.situacao == "pendente" and e.tentativas == 1
    import hmac as hmac_mod
    t = chamadas[0]["X-PCPR-Assinatura"].split(",")[0][2:]
    esperado = hmac_mod.new(b"segredo-de-teste", t.encode() + b"." + json.dumps(
        e.corpo, ensure_ascii=False, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    assert chamadas[0]["X-PCPR-Assinatura"].endswith(esperado)
    EventoIntegracao.objects.filter(pk=e.pk).update(disponivel_em=timezone.now())
    assert eventos.processar_um(postar=lambda u, corpo, cab: 401)
    e.refresh_from_db()
    assert e.situacao == "configuracao"
    assert ExcecaoAutomacao.objects.filter(chave="eventos-n8n:401").exists()


def test_manutencao_validade_orfaos_e_retencao(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(expira_em=timezone.now() - timedelta(1))
    chaves.desligar_tudo(c.usuarios["admin"], "teste")
    assert manutencao.expirar_vencidas() == 1  # vale mesmo com a automação desligada
    StatusEntrega.objects.create(mensagem_id="wamid.ORFAO", status="entregue")
    StatusEntrega.objects.filter(mensagem_id="wamid.ORFAO").update(
        registrado_em=timezone.now() - timedelta(hours=2))
    assert manutencao.reconciliar() == 1
    # Já tem exceção: não entra de novo — e, resolvida por uma pessoa, não reabre.
    assert manutencao.reconciliar() == 0
    ExcecaoAutomacao.objects.filter(chave="orfao:wamid.ORFAO").update(
        situacao=ExcecaoAutomacao.Situacao.RESOLVIDA)
    assert manutencao.reconciliar() == 0
    assert ExcecaoAutomacao.objects.get(chave="orfao:wamid.ORFAO").situacao == "resolvida"
    from gestao.automacao.models import ConteudoComunicacao
    ConteudoComunicacao.objects.create(comunicacao=aviso, texto="x",
                                       expira_em=timezone.now() - timedelta(1))
    resultado = manutencao.purgar()
    assert resultado["textos"] == 1


def test_limite_por_hora(c, settings):
    settings.WHATSAPP = {"limite_por_hora": "1"}
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c, dias_prazo=5)
    _liberar(c, dias_prazo=7)  # duas comunicações (versões diferentes)
    espiao = Espiao()
    while entrega.processar_uma(porta=espiao):
        pass
    assert len(espiao.envios) == 1


def test_comando_do_worker_uma_vez(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    call_command("processar_automacao", "--uma-vez")
    assert _aviso(c).situacao == S.ENVIADA


# ------------------------------------------------------------------ fluxo pelo WhatsApp
def test_lembrete_pendente_encerrado_pelo_comprovante_do_whatsapp(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c, dias_prazo=2)
    entrega.processar_uma(porta=Espiao())
    assert viagens_whatsapp.agendar_lembretes() == 1
    simulador.simular_resposta(c.usuarios["operador"], _aviso(c).pk, conteudo=PDF,
                               nome="c.pdf")
    _processar_entradas()
    recebimentos.processar_um()
    lembrete = Comunicacao.objects.get(tipo=viagens_whatsapp.LEMBRETE)
    assert lembrete.situacao == S.OBSOLETA and "WhatsApp" in lembrete.motivo


def test_resposta_ao_aviso_antigo_vai_para_a_prestacao_certa(c):
    """Duas comunicações abertas para o mesmo contato: a resposta que CITA a mais antiga vai
    para a prestação dela, não para a mais recente."""
    _ligar(c, *TODOS)
    contato = _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    antigo = _aviso(c)
    outra_ps = (PrestacaoServidor.objects.filter(prestacao=c.ps.prestacao)
                .exclude(pk=c.ps.pk).first())
    recente = Comunicacao.objects.create(
        tipo=viagens_whatsapp.AVISO, fluxo="diarias_liberadas", servidor=outra_ps.servidor,
        contato=contato, recurso=f"{viagens_whatsapp.RECURSO}:{outra_ps.pk}",
        contexto={"ps": outra_ps.pk}, chave="teste:recente", situacao=S.ENVIADA,
        mensagem_id="wamid.RECENTE", aceita_resposta=viagens_whatsapp.COMPROVANTE,
        resposta_ate=timezone.now() + timedelta(days=5),
        enviada_em=timezone.now() + timedelta(minutes=1), criada_por=c.usuarios["operador"])
    simulador.simular_resposta(c.usuarios["operador"], antigo.pk, conteudo=PDF, nome="c.pdf")
    _processar_entradas()
    recebimentos.processar_um()
    r = Recebimento.objects.get()
    assert r.comunicacao_id == antigo.pk != recente.pk
    assert AnexoPrestacao.objects.filter(servidor=c.ps, tipo="comprovante").exists()
    assert not AnexoPrestacao.objects.filter(servidor=outra_ps, tipo="comprovante").exists()


def test_arquivo_grande_e_comprovante_repetido(c, settings):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=PDF + b"0" * 4096,
                               nome="g.pdf")
    settings.WHATSAPP = {"tamanho_maximo_midia": str(1024)}
    _processar_entradas()
    recebimentos.processar_um()
    assert Recebimento.objects.get().situacao == Recebimento.Situacao.RECUSADO
    settings.WHATSAPP = {}
    for _ in range(2):  # o mesmo comprovante duas vezes: um anexo só
        simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=PDF, nome="c.pdf")
        _processar_entradas()
        while recebimentos.processar_um():
            pass
    assert AnexoPrestacao.objects.filter(servidor=c.ps, tipo="comprovante",
                                         removido_em=None).count() == 1


REAL = {"modo": "cloud_api", "phone_number_id": "123", "access_token": "tok",
        "app_secret": "segredo-de-teste", "verify_token": "verifica"}


@override_settings(WHATSAPP=REAL)
def test_webhook_corpo_reserializado_e_grande(client):
    from gestao.automacao.models import EntradaWebhook

    corpo = webhook.montar_status(mensagem_id="wamid.Z", status="sent", destinatario=E164)
    assinatura = webhook.assinar(corpo, "segredo-de-teste")
    reserializado = json.dumps(json.loads(corpo), indent=2).encode()
    assert client.post("/integracoes/whatsapp/webhook/", reserializado,
                       content_type="application/json",
                       HTTP_X_HUB_SIGNATURE_256=assinatura).status_code == 401
    grande = b" " * (webhook.TAMANHO_MAXIMO + 10)
    r = client.post("/integracoes/whatsapp/webhook/", grande, content_type="application/json",
                    HTTP_X_HUB_SIGNATURE_256=webhook.assinar(grande, "segredo-de-teste"))
    assert r.status_code in (400, 413)
    assert not EntradaWebhook.objects.exists()


def test_check_de_cloud_api_incompleta():
    from gestao.automacao.checks import verificar_canal

    with override_settings(APP_ENV="lab", WHATSAPP={"modo": "cloud_api"}):
        assert any(e.id == "automacao.E003" for e in verificar_canal(None))
    with override_settings(APP_ENV="lab", WHATSAPP=REAL):
        assert not verificar_canal(None)


# ------------------------------------------------------------------ revisão de UX (P1)
def test_painel_avisa_cada_fluxo_desligado(c):
    op = _cliente(c.usuarios["operador"])
    assert "Nada sai agora: a automação está desligada" in op.get("/automacao/").content.decode()
    _ligar(c, "diarias_liberadas")
    html = op.get("/automacao/").content.decode()
    assert "Nada sai agora" not in html
    assert "fluxos desligados" in html and "Lembretes de comprovante" in html


def test_aprovacao_em_lote_na_aba_aguardando(c):
    _ligar(c, *TODOS, modo="assistido")
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    entrega.processar_uma(porta=Espiao())
    aviso.refresh_from_db()
    assert aviso.situacao == S.AGUARDANDO_APROVACAO
    op = _cliente(c.usuarios["operador"])
    assert "Para aprovar" in op.get("/automacao/").content.decode()
    html = op.get("/automacao/comunicacoes/?aba=aprovar").content.decode()
    assert f'name="ids" value="{aviso.pk}"' in html and "data-confirmar=" in html
    # Outra unidade não aprova pelo lote (a regra é a da aprovação individual).
    _cliente(c.usuarios["outra"]).post("/automacao/comunicacoes/aprovar/", {"ids": [aviso.pk]})
    aviso.refresh_from_db()
    assert aviso.situacao == S.AGUARDANDO_APROVACAO
    r = op.post("/automacao/comunicacoes/aprovar/", {"ids": [aviso.pk, 999999]})
    assert r.status_code == 302 and r["Location"].endswith("?aba=aprovar")
    aviso.refresh_from_db()
    assert aviso.situacao == S.AGENDADA and aviso.aprovada_por == c.usuarios["operador"]


def test_revogacao_em_massa_mostra_quantos_e_exige_motivo(c):
    from gestao.automacao import links

    links.criar(escopo="km", recurso="viagens.diario:1", servidor_id=c.ps.servidor_id)
    admin = _cliente(c.usuarios["admin"])
    html = admin.get("/automacao/links/").content.decode()
    assert "<strong>1</strong> link vigente" in html and "data-confirmar-perigo" in html
    admin.post("/automacao/links/revogar-em-massa/", {"horas": "24"})  # sem motivo: nada
    assert LinkAcesso.objects.get().revogado_em is None
    admin.post("/automacao/links/revogar-em-massa/", {"horas": "24", "motivo": "vazamento"})
    link = LinkAcesso.objects.get()
    assert link.revogado_em is not None and link.motivo_revogacao == "vazamento"


def test_tela_de_aprovacoes_confirma_e_recusa_com_motivo(c):
    _ligar(c, *TODOS, "ferramentas")
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    pedido = ferramentas.executar("comunicacoes.cancelar", {"comunicacao": aviso.pk},
                                  usuario=c.usuarios["gestor"], origem="tela").aprovacao
    op = _cliente(c.usuarios["operador"])
    html = op.get("/automacao/aprovacoes/").content.decode()
    assert "data-confirmar=" in html and "data-pedir-motivo=" in html
    assert 'id="dialogo-motivo"' in html
    op.post(f"/automacao/aprovacoes/{pedido.pk}/recusar/", {"motivo": "Não era para cancelar"})
    pedido.refresh_from_db()
    aviso.refresh_from_db()
    assert pedido.situacao == PedidoAprovacao.Situacao.RECUSADO
    assert pedido.motivo == "Não era para cancelar" and aviso.situacao != S.CANCELADA


def _validador_do_contrato():
    """O validador stdlib do protótipo (docs/automacao/prototipo/validar_esquema.py)."""
    import importlib.util
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[3] / "docs" / "automacao"
    spec = importlib.util.spec_from_file_location(
        "validar_esquema_contrato", raiz / "prototipo" / "validar_esquema.py")
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    esquema = json.loads((raiz / "contratos" / "evento-integracao.schema.json")
                         .read_text(encoding="utf-8"))
    return modulo.validar, esquema


@override_settings(N8N_EVENTOS_URL="http://n8n.invalid/webhook/pcpr-eventos",
                   N8N_EVENTOS_SEGREDO="segredo-de-teste")
def test_envelopes_emitidos_seguem_o_esquema_do_contrato(c):
    """D1 da bateria contra a API real: fluxo em [a-z0-9-], tipo_comunicacao do enum e
    automacao.religada/desligada só com `fluxo` (nulo = chave geral)."""
    validar, esquema = _validador_do_contrato()
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    chaves.desligar_tudo(c.usuarios["admin"], "teste")
    corpos = list(EventoIntegracao.objects.values_list("corpo", flat=True))
    assert {"comunicacao.agendada", "automacao.religada", "automacao.desligada"} <= {
        e["tipo"] for e in corpos}
    for corpo in corpos:
        assert validar(corpo, esquema) == [], corpo["tipo"]
    agendado = next(e for e in corpos if e["tipo"] == "comunicacao.agendada")
    assert agendado["dados"]["tipo_comunicacao"] == "mensagem_saque"
    assert agendado["dados"]["fluxo"] == "diarias-liberadas"


def test_todo_tipo_registrado_tem_par_no_enum_do_contrato():
    from gestao.automacao import contrato, ganchos

    _, esquema = _validador_do_contrato()
    enum = set(esquema["$defs"]["dados.comunicacao.agendada"]["properties"]
               ["tipo_comunicacao"]["enum"])
    for t in ganchos.tipos():
        assert t.chave in contrato.TIPOS_CONTRATO, t.chave
        assert contrato.TIPOS_CONTRATO[t.chave] in enum, t.chave


# ------------------------------------------------------------------ bateria contra a API real
def _v1(n8n, conteudo, mid="wamid.V1", indice=0, chave=None):
    from gestao.automacao import dominio

    return Client().post("/api/automacao/v1/recebimentos", {
        "arquivo": _arquivo(conteudo), "canal": "whatsapp", "mensagem_id_canal": mid,
        "anexo_indice": str(indice), "total_anexos": "1", "remetente": E164,
        "recebido_em": timezone.now().isoformat(),
        "sha256": hashlib.sha256(conteudo).hexdigest()},
        HTTP_AUTHORIZATION=f"Bearer {n8n}",
        HTTP_IDEMPOTENCY_KEY=chave or dominio.chave_recebimento("whatsapp", mid, indice))


def _com_recebimentos(n8n):
    from gestao.automacao.models_api import CredencialIntegracao

    cred = CredencialIntegracao.objects.get(nome="n8n")
    cred.escopos = [*cred.escopos, "recebimentos:criar"]
    cred.save(update_fields=["escopos"])


def test_mesma_chave_com_outro_arquivo_e_409_e_canal_bloqueado_e_409(c, n8n):
    """D4 e D3: o contrato pede 409 conflito_de_versao (não o 422 genérico) e 409
    canal_bloqueado com o canal de entrada bloqueado; desligado é 423 (o canal reentrega)."""
    _com_recebimentos(n8n)
    assert _v1(n8n, PDF).status_code == 202
    assert _v1(n8n, PDF).status_code == 202  # a mesma: repetição sem efeito
    outro = _v1(n8n, PDF + b"%%mudou")
    assert outro.status_code == 409 and outro.json()["codigo"] == "conflito_de_versao"
    assert Recebimento.objects.filter(mensagem_id="wamid.V1").count() == 1
    admin = c.usuarios["admin"]
    chaves.alterar(admin, chaves.nome_canal("whatsapp"), estado="bloqueada")
    r = _v1(n8n, PDF, mid="wamid.V1B")
    assert r.status_code == 409 and r.json()["codigo"] == "canal_bloqueado"
    chaves.alterar(admin, chaves.nome_canal("whatsapp"), estado="desligada")
    assert _v1(n8n, PDF, mid="wamid.V1C").status_code == 423
    assert not Recebimento.objects.filter(mensagem_id__in=("wamid.V1B", "wamid.V1C")).exists()


def test_id_longo_do_canal_nao_e_truncado(c, n8n):
    """Dois ids de 290 caracteres com o mesmo começo são dois recebimentos (antes, cortados
    em 128, viravam o mesmo)."""
    _com_recebimentos(n8n)
    base = "wamid." + "L" * 270
    for fim in ("AAAAAAAAAAAAAA", "BBBBBBBBBBBBBB"):
        assert _v1(n8n, PDF + fim.encode(), mid=base + fim).status_code == 202
    assert Recebimento.objects.filter(mensagem_id__startswith=base).count() == 2


def test_status_repetido_com_outro_horario_nao_e_422(c, n8n):
    """D2: o provedor repete o mesmo status com outro horário; a chave do contrato
    (entrega:<id>:<wamid>:<status>) é a mesma → 200 sem efeito, nunca 422."""
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(situacao=S.ENVIADA,
                                                   mensagem_id="wamid.D2")
    chave = f"entrega:{aviso.pk}:wamid.D2:lida"
    for minutos in (0, 3):
        r = _post(n8n, f"/comunicacoes/{aviso.pk}/entrega",
                  {"provedor_mensagem_id": "wamid.D2", "status": "lida",
                   "ocorrido_em": (timezone.now() - timedelta(minutes=minutos)).isoformat()},
                  chave)
        assert r.status_code == 200, r.content
    aviso.refresh_from_db()
    assert aviso.entrega == "lida"


def test_resposta_que_cita_aviso_vencido_vai_para_uma_pessoa(c):
    """A resposta que cita um pedido de arquivo cujo prazo de resposta já passou não entra
    sozinha no assunto velho: fica para uma pessoa decidir o destino."""
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(
        resposta_ate=timezone.now() - timedelta(days=1))
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=PDF, nome="c.pdf")
    _processar_entradas()
    recebimentos.processar_um()
    r = Recebimento.objects.get()
    assert r.comunicacao_id == aviso.pk  # a citação fica registrada…
    assert r.situacao != Recebimento.Situacao.ASSOCIADO  # …mas não associa sozinha
    assert not AnexoPrestacao.objects.filter(servidor=c.ps, tipo="comprovante").exists()


# ------------------------------------------------------------------ revisão do PR #24 (Codex)
def test_status_orfao_existente_e_religado_na_reentrega(c):
    """Status que chegou antes do resultado e escapou da varredura de `_aceita` (corrida):
    a reentrega da Meta, com a comunicação já conhecida, religa e aplica."""
    from gestao.automacao import entrada as entrada_mod
    from gestao.integracoes.whatsapp.porta import StatusRecebido

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    orfao = StatusEntrega.objects.create(mensagem_id=aviso.mensagem_id, status="lida",
                                         comunicacao=None)
    st = StatusRecebido(mensagem_id=aviso.mensagem_id, status="read",
                        ocorrido_em=timezone.now())
    from django.db import transaction as tx
    with tx.atomic():
        entrada_mod.registrar_status(st)
    orfao.refresh_from_db()
    aviso.refresh_from_db()
    assert orfao.comunicacao_id == aviso.pk and aviso.entrega == "lida"


def test_v1_recusa_identificacao_invalida_e_chave_de_outro_recebimento(c, n8n):
    _com_recebimentos(n8n)
    sem_id = Client().post("/api/automacao/v1/recebimentos", {
        "arquivo": _arquivo(PDF), "canal": "whatsapp", "mensagem_id_canal": "",
        "anexo_indice": "0", "total_anexos": "1", "remetente": E164,
        "sha256": hashlib.sha256(PDF).hexdigest()},
        HTTP_AUTHORIZATION=f"Bearer {n8n}", HTTP_IDEMPOTENCY_KEY="receb:whatsapp::0-xxxxxxxx")
    assert sem_id.status_code == 422
    negativo = _post(n8n, "/recebimentos/sem-arquivo", {
        "canal": "whatsapp", "mensagem_id_canal": "wamid.NEG", "anexo_indice": -1,
        "total_anexos": 1, "remetente": E164, "motivo": "sem_anexo"}, "receb:whatsapp:wamid.NEG:-1")
    assert negativo.status_code == 422
    # A mesma Idempotency-Key reaproveitada para OUTRO recebimento: 422 (não executa de novo).
    chave = "receb:whatsapp:wamid.REUSO:0"
    assert _v1(n8n, PDF, mid="wamid.REUSO", chave=chave).status_code == 202
    assert _v1(n8n, PDF + b"%%x", mid="wamid.OUTRO", chave=chave).status_code == 422
    assert not Recebimento.objects.filter(mensagem_id="wamid.OUTRO").exists()


def test_sem_arquivo_nao_abre_atendimento_nem_responde_duas_vezes(c, n8n):
    _com_recebimentos(n8n)
    r = _post(n8n, "/recebimentos/sem-arquivo", {
        "canal": "whatsapp", "mensagem_id_canal": "wamid.SEMARQ", "anexo_indice": 0,
        "total_anexos": 1, "remetente": E164, "motivo": "acima_do_limite",
        "recebido_em": timezone.now().isoformat()},
        "receb:whatsapp:wamid.SEMARQ:0")
    assert r.status_code in (200, 201, 202), r.content
    receb = Recebimento.objects.get(mensagem_id="wamid.SEMARQ")
    assert receb.situacao == Recebimento.Situacao.RECUSADO
    assert not ExcecaoAutomacao.objects.filter(chave=f"atendimento:receb:{receb.pk}").exists()
    tipos = set(Comunicacao.objects.filter(em_resposta_a=receb).values_list("tipo", flat=True))
    assert tipos == {"automacao.arquivo_recusado"}


def test_contato_com_a_outra_forma_do_celular_e_recusado(c):
    """Duas pessoas com o mesmo celular com e sem o 9º dígito: o 2º cadastro é recusado
    (as respostas cairiam no servidor errado)."""
    from gestao.automacao import contatos as contatos_mod
    from gestao.automacao import dominio
    from gestao.cadastros.models import Servidor

    _contato_ativo(c)
    variantes = dominio.variantes(E164) - {E164}
    assert variantes
    outro = Servidor.objects.filter(ativo=True).exclude(pk=c.ps.servidor_id).first()
    outro.telefone = next(iter(variantes))[2:]  # o cadastro guarda DDD + número, sem o 55
    outro.save(update_fields=["telefone"])
    with pytest.raises(contatos_mod.ContatoInvalido):
        contatos_mod.cadastrar(c.usuarios["operador"], outro.pk)


def test_entregue_em_fica_com_a_hora_real_mesmo_se_a_leitura_chegar_antes(c):
    from django.db import transaction as tx

    from gestao.automacao import entrada as entrada_mod
    from gestao.integracoes.whatsapp.porta import StatusRecebido

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    agora = timezone.now()
    with tx.atomic():
        entrada_mod.registrar_status(StatusRecebido(mensagem_id=aviso.mensagem_id, status="read",
                                                    ocorrido_em=agora))
        entrada_mod.registrar_status(StatusRecebido(
            mensagem_id=aviso.mensagem_id, status="delivered",
            ocorrido_em=agora - timedelta(minutes=3)))
    aviso.refresh_from_db()
    assert aviso.entregue_em == agora - timedelta(minutes=3) and aviso.lida_em == agora


def test_remover_testador_cancela_o_que_estava_para_sair(c, n8n):
    from gestao.automacao import contatos as contatos_mod
    from gestao.automacao.models import DestinatarioAutorizado

    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(situacao=S.RESERVADA)
    d = DestinatarioAutorizado.objects.get(removido_em__isnull=True)
    contatos_mod.remover_testador(c.usuarios["admin"], d.pk)
    aviso.refresh_from_db()
    assert aviso.situacao == S.CANCELADA


def test_lidas_hoje_conta_pela_hora_da_leitura(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    ontem = timezone.now() - timedelta(days=1)
    Comunicacao.objects.filter(pk=aviso.pk).update(
        situacao=S.ENVIADA, enviada_em=ontem, entrega="lida", lida_em=timezone.now())
    resposta = _cliente(c.usuarios["operador"]).get("/automacao/")
    assert resposta.context["numeros"]["lidas_hoje"] == 1


def test_status_de_tentativa_antiga_nao_confirma_a_atual(c):
    from django.db import transaction as tx

    from gestao.automacao import entrada as entrada_mod
    from gestao.integracoes.whatsapp.porta import StatusRecebido

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(situacao=S.RESERVADA, tentativas=2,
                                                   mensagem_id="")
    with tx.atomic():
        entrada_mod.registrar_status(StatusRecebido(
            mensagem_id="wamid.T1", status="delivered", ocorrido_em=timezone.now(),
            referencia=f"com:{aviso.pk}:t1"))
    aviso.refresh_from_db()
    assert aviso.mensagem_id == "" and aviso.situacao == S.RESERVADA
    assert StatusEntrega.objects.get(mensagem_id="wamid.T1").comunicacao_id is None


def test_falha_que_chegou_antes_do_aceite_continua_falha(c):
    from gestao.automacao.models import TentativaEntrega
    from gestao.integracoes.whatsapp.porta import Envio, Origem

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(situacao=S.FALHOU, entrega="falhou")
    t = TentativaEntrega.objects.create(comunicacao=aviso, numero=1, chave="t-r7-1",
                                        adaptador="n8n")
    entrega.registrar_resultado(t.pk, envio=Envio(mensagem_id="wamid.R7",
                                                  origem=Origem.CLOUD_API), origem="n8n")
    aviso.refresh_from_db()
    assert aviso.situacao == S.FALHOU and aviso.mensagem_id == "wamid.R7"


def test_lembrete_reservado_fica_obsoleto_quando_o_assunto_resolve(c):
    from gestao.automacao import comunicacoes as com_mod

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = _aviso(c)
    Comunicacao.objects.filter(pk=aviso.pk).update(situacao=S.RESERVADA)
    from django.db import transaction as tx
    with tx.atomic():
        com_mod.encerrar_relacionadas(aviso.recurso, (aviso.tipo,), "O comprovante chegou.")
    aviso.refresh_from_db()
    assert aviso.situacao == S.OBSOLETA and aviso.reservada_ate is None


def test_contato_nao_identifica_servidor_desativado_ou_com_outro_telefone(c):
    from django.db import transaction as tx

    from gestao.automacao import entrada as entrada_mod
    from gestao.integracoes.whatsapp.porta import MensagemRecebida

    contato = _contato_ativo(c)
    m = MensagemRecebida(mensagem_id="wamid.ID1", tipo="text", recebida_em=timezone.now(),
                         remetente=E164)
    with tx.atomic():
        assert entrada_mod.identificar(m).pk == contato.pk
    servidor = contato.servidor
    servidor.telefone = "41988887777"  # o cadastro mudou: o número antigo não fala por ele
    servidor.save(update_fields=["telefone"])
    with tx.atomic():
        assert entrada_mod.identificar(m) is None
    servidor.telefone, servidor.ativo = E164[2:], False
    servidor.save(update_fields=["telefone", "ativo"])
    with tx.atomic():
        assert entrada_mod.identificar(m) is None


def test_arquivo_gravado_e_apagado_se_a_associacao_falhar(c, monkeypatch):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    aviso = _aviso(c)
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=PDF, nome="c.pdf")
    _processar_entradas()
    gravados: list[tuple] = []

    def falha(r):
        gravados.append((r.arquivo.storage, r.arquivo.name))
        raise RuntimeError("falha simulada depois de gravar")

    monkeypatch.setattr(recebimentos, "tentar_associar", falha)
    recebimentos.processar_um()
    (storage, nome), = gravados
    assert nome and not storage.exists(nome)
    assert not Recebimento.objects.get().arquivo  # a transação desfez o registro


# ------------------------------------------------------------------ 9ª revisão
def test_repeticao_da_reserva_recusa_a_versao_antiga(c, n8n):
    """A resposta da reserva se perdeu e o assunto mudou antes da repetição (outra versão já
    está na fila): a repetição revalida a versão como a 1ª reserva e não devolve a velha."""
    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-versao-velha"
    assert _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).status_code == 200
    Comunicacao.objects.filter(pk=aviso.pk).update(versao="versao-anterior")
    r = _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave)
    assert r.status_code == 409 and r.json()["codigo"] == "obsoleta", r.content
    assert "reserva" not in r.json()  # nada de conteúdo novo para a comunicação velha
    aviso.refresh_from_db()
    assert aviso.situacao == S.OBSOLETA and aviso.reservada_ate is None


def test_repeticao_da_reserva_recusa_contato_que_deixou_de_valer(c, n8n):
    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-telefone-novo"
    assert _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).status_code == 200
    servidor = c.ps.servidor
    servidor.telefone = "41988887777"  # o cadastro mudou entre a reserva e a repetição
    servidor.save(update_fields=["telefone"])
    r = _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave)
    assert r.status_code == 409 and r.json()["codigo"] == "regra_violada", r.content
    aviso.refresh_from_db()
    assert aviso.situacao == S.RECUSADA and "telefone" in aviso.motivo


def test_repeticao_da_reserva_com_a_chave_desligada_e_423(c, n8n):
    aviso = _aviso(c)
    chave = f"reserva:{aviso.pk}:v1:exec-desligada"
    assert _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave).status_code == 200
    chaves.alterar(c.usuarios["admin"], chaves.nome_fluxo("diarias_liberadas"),
                   estado="desligada")
    r = _post(n8n, f"/comunicacoes/{aviso.pk}/reservar", {}, chave)
    assert r.status_code == 423, r.content


def _arquivo_recebido(c):
    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    entrega.processar_uma(porta=Espiao())
    simulador.simular_resposta(c.usuarios["operador"], _aviso(c).pk, conteudo=PDF,
                               nome="c.pdf")
    _processar_entradas()
    return Recebimento.objects.get()


def test_credencial_vencida_no_download_bloqueia_o_canal(c):
    """Token vencido ao buscar a mídia: o mesmo tratamento do envio (canal bloqueado e
    exceção para quem administra), sem gastar a tentativa do arquivo — e nada mais se baixa
    até o canal ser religado."""
    from gestao.automacao.models import ChaveAutomacao
    from gestao.integracoes.whatsapp import erros as erros_canal
    from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado

    class TokenVencido(AdaptadorSimulado):
        def baixar_midia(self, anexo, limite):
            raise erros_canal.CanalBloqueado("Token de acesso vencido.", "190")

    r = _arquivo_recebido(c)
    assert recebimentos.processar_um(TokenVencido())
    r.refresh_from_db()
    assert r.situacao == Recebimento.Situacao.IDENTIFICADO and not r.arquivo
    assert r.tentativas == 0 and r.reservado_ate is None
    canal = ChaveAutomacao.objects.get(nome=chaves.nome_canal("whatsapp"))
    assert canal.estado == ChaveAutomacao.Estado.BLOQUEADA
    assert ExcecaoAutomacao.objects.filter(tipo=ExcecaoAutomacao.Tipo.CANAL,
                                           chave="canal:whatsapp:190").exists()
    assert recebimentos.reservar() is None
    chaves.alterar(c.usuarios["admin"], chaves.nome_canal("whatsapp"), estado="ligada")
    assert recebimentos.processar_um()
    r.refresh_from_db()
    assert r.arquivo and r.situacao == Recebimento.Situacao.ASSOCIADO, r.motivo


def test_midia_do_simulador_sai_depois_de_baixada_e_a_orfa_com_a_retencao(c):
    import os

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from gestao.integracoes.whatsapp.adaptadores import PREFIXO_SIMULADO

    r = _arquivo_recebido(c)
    origem = PREFIXO_SIMULADO + r.midia_id
    assert default_storage.exists(origem)
    assert recebimentos.processar_um()
    r.refresh_from_db()
    assert r.arquivo and not default_storage.exists(origem)
    # A que nunca foi baixada (quarentena, tentativas esgotadas) sai com a retenção.
    orfa = default_storage.save(PREFIXO_SIMULADO + "SIMORFA" + r.midia_id, ContentFile(PDF))
    recente = default_storage.save(PREFIXO_SIMULADO + "SIMNOVA" + r.midia_id, ContentFile(PDF))
    antiga = (timezone.now() - entrega.retencao() - timedelta(days=1)).timestamp()
    os.utime(default_storage.path(orfa), (antiga, antiga))
    try:
        assert manutencao.purgar()["midia_simulada"] >= 1
        assert not default_storage.exists(orfa) and default_storage.exists(recente)
    finally:
        default_storage.delete(recente)


def test_envio_manual_abre_a_janela_de_resposta(c):
    """Contingência: a pessoa mandou à mão o pedido do comprovante. O arquivo que o servidor
    devolve (sem citar mensagem, que não existe no canal) acha o pedido pela janela de
    resposta e entra na prestação, como depois de um envio pelo provedor."""
    from gestao.automacao import comunicacoes

    _ligar(c, *TODOS)
    _contato_ativo(c)
    _liberar(c)
    aviso = comunicacoes.registrar_envio_manual(c.usuarios["operador"], _aviso(c).pk)
    assert aviso.situacao == S.MANUAL and aviso.aceita_resposta
    assert aviso.resposta_ate and aviso.resposta_ate > timezone.now()
    simulador.simular_resposta(c.usuarios["operador"], aviso.pk, conteudo=PDF, nome="c.pdf")
    _processar_entradas()
    r = Recebimento.objects.get()
    assert r.comunicacao_id == aviso.pk
    assert recebimentos.processar_um()
    r.refresh_from_db()
    assert r.situacao == Recebimento.Situacao.ASSOCIADO, r.motivo


def test_mesma_mensagem_gravada_por_outra_entrega_ao_mesmo_tempo_e_repeticao(c, monkeypatch):
    """Duas entregas da mesma mensagem passam juntas pela consulta de repetição: a que perde
    a corrida esbarra na chave única e é tratada como repetição — sem desfazer o lote."""
    from django.db import transaction as tx

    from gestao.automacao import dominio
    from gestao.automacao import entrada as entrada_mod
    from gestao.automacao.models import CANAL_WHATSAPP
    from gestao.integracoes.whatsapp.porta import MensagemRecebida

    _contato_ativo(c)
    m = MensagemRecebida(mensagem_id="wamid.CORRIDA", tipo="text", recebida_em=timezone.now(),
                         remetente=E164, texto="Bom dia")
    identificar = entrada_mod.identificar

    def outra_entrega_grava_antes(msg):
        contato = identificar(msg)
        Recebimento.objects.create(
            mensagem_id=msg.mensagem_id, tipo=Recebimento.Tipo.TEXTO,
            chave=dominio.chave_recebimento(CANAL_WHATSAPP, msg.mensagem_id, 0))
        return contato

    monkeypatch.setattr(entrada_mod, "identificar", outra_entrega_grava_antes)
    with tx.atomic():
        assert entrada_mod.registrar_mensagem(m) is None
        # A transação do lote continua usável (o savepoint desfez só o insert repetido).
        assert Recebimento.objects.filter(mensagem_id="wamid.CORRIDA").count() == 1


# ------------------------------------------------------------------ 10ª revisão
def test_falha_passageira_no_download_espera_antes_de_tentar_de_novo(c):
    """Queda breve da Meta: o arquivo não volta a ser elegível na hora (o worker gastaria as
    4 tentativas em segundos e recusaria o arquivo) — espera e depois baixa."""
    from gestao.integracoes.whatsapp import erros as erros_canal
    from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado

    class MetaFora(AdaptadorSimulado):
        def baixar_midia(self, anexo, limite):
            raise erros_canal.FalhaTemporaria("Sem conexão com a Meta.", "rede")

    r = _arquivo_recebido(c)
    assert recebimentos.processar_um(MetaFora())
    r.refresh_from_db()
    assert r.tentativas == 1 and r.reservado_ate > timezone.now() + timedelta(minutes=1)
    assert not recebimentos.processar_um(MetaFora())  # ainda esperando: nada é tentado
    r.refresh_from_db()
    assert r.tentativas == 1 and r.situacao == Recebimento.Situacao.IDENTIFICADO
    Recebimento.objects.filter(pk=r.pk).update(reservado_ate=timezone.now() - timedelta(1))
    assert recebimentos.processar_um()
    r.refresh_from_db()
    assert r.arquivo and r.tentativas == 2


def test_arquivo_da_v1_sai_do_storage_se_a_transacao_desfizer_o_registro(c, monkeypatch):
    _contato_ativo(c)
    gravados: list[tuple] = []

    def falha(r, motivo, **_):
        gravados.append((r.arquivo.storage, r.arquivo.name))
        raise RuntimeError("falha simulada depois de gravar")

    monkeypatch.setattr(recebimentos, "_pedir_destino", falha)
    with pytest.raises(RuntimeError):
        recebimentos.receber_arquivo(mensagem_id="wamid.V1FALHA", indice=0, remetente=E164,
                                     conteudo=PDF, nome="c.pdf", recebido_em=timezone.now())
    (storage, nome), = gravados
    assert nome and not storage.exists(nome)
    assert not Recebimento.objects.filter(mensagem_id="wamid.V1FALHA").exists()


def test_falha_de_conta_so_no_erro_do_status_bloqueia_o_canal(c):
    """Envio assíncrono que falhou por problema da conta (token vencido, 190): a Meta avisa
    só no `statuses[].errors` — o canal bloqueia como no envio síncrono."""
    from gestao.automacao import entrada as entrada_mod
    from gestao.automacao.models import ChaveAutomacao

    _ligar(c, *TODOS)
    entrada_mod.registrar_entrada(webhook.montar_status(
        mensagem_id="wamid.CONTA", status="failed", destinatario=E164, erro_codigo="190"),
        origem="simulador")
    _processar_entradas()
    canal = ChaveAutomacao.objects.get(nome=chaves.nome_canal("whatsapp"))
    assert canal.estado == ChaveAutomacao.Estado.BLOQUEADA
    assert ExcecaoAutomacao.objects.filter(tipo=ExcecaoAutomacao.Tipo.CANAL,
                                           chave="canal:whatsapp:190").exists()
    # Falha de uma mensagem só (número sem WhatsApp) não bloqueia nada.
    chaves.alterar(c.usuarios["admin"], chaves.nome_canal("whatsapp"), estado="ligada")
    entrada_mod.registrar_entrada(webhook.montar_status(
        mensagem_id="wamid.UMA", status="failed", destinatario=E164, erro_codigo="131026"),
        origem="simulador")
    _processar_entradas()
    canal.refresh_from_db()
    assert canal.estado == ChaveAutomacao.Estado.LIGADA
