"""API de automação v1 com o transporte pelo n8n: credencial por escopo e ambiente,
idempotência (repetição devolve a mesma resposta; mesma chave com outra requisição = 422),
reserva com os códigos do contrato, resultado e entrega, 423 só no que cria efeito novo,
delegação emitida pelo PCPR (nunca um cabeçalho livre) e aprovação humana do irreversível.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client, override_settings
from django.utils import timezone

from gestao.automacao import chaves, contatos, entrega, ferramentas
from gestao.automacao.api import credenciais, delegacoes
from gestao.automacao.models import Comunicacao, ContatoVerificado, ExcecaoAutomacao
from gestao.automacao.models_api import ExecucaoFerramenta, PedidoAprovacao
from gestao.identidade.models import Usuario
from gestao.viagens import prestacao
from gestao.viagens.models import PrestacaoServidor

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
URL = "/api/automacao/v1"
E164 = "5541999990001"


@pytest.fixture(autouse=True)
def _sem_trava(monkeypatch):
    monkeypatch.setattr(entrega, "VERIFICAR_TRANSACAO", False)


@pytest.fixture
def c(settings):
    settings.AUTOMACAO_TRANSPORTE = "n8n"
    # Fora da janela de 24 h só sai modelo aprovado: o LAB configura o nome dele.
    settings.WHATSAPP = {"modelos": "viagens.diarias_liberadas=diarias_teste:pt_BR"}
    cen = cenario_completo()
    admin = Usuario.objects.create_user("admin-api", "admin-api@pc.pr.gov.br", "x", nome="Admin")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    cen.usuarios["admin"] = admin
    ps = (PrestacaoServidor.objects.filter(prestacao__oficio_id=cen.ids["oficio_emitido"])
          .select_related("servidor").order_by("servidor__nome").first())
    ps.servidor.telefone = "41999990001"
    ps.servidor.save(update_fields=["telefone"])
    for nome in (chaves.GERAL, chaves.nome_canal("whatsapp"),
                 chaves.nome_fluxo("diarias_liberadas"), chaves.nome_fluxo("ferramentas")):
        chaves.alterar(admin, nome, estado="ligada", modo="automatico")
    op = cen.usuarios["operador"]
    contato = contatos.cadastrar(op, ps.servidor_id)
    contatos.confirmar_numero(op, contato.pk)
    contatos.registrar_optin(op, contato.pk, ContatoVerificado.OrigemOptin.FORMULARIO)
    contatos.autorizar_testador(admin, E164, "Testador")
    hoje = timezone.localdate()
    prestacao.salvar_solicitacao(op, ps.pk, numero="1", liberacao=hoje,
                                 prazo=hoje + timedelta(days=5))
    cen.ps = ps
    cen.com = Comunicacao.objects.get(tipo="viagens.diarias_liberadas")
    _, cen.token = credenciais.emitir(admin, nome="n8n LAB", tipo="transporte")
    return cen


def _post(c, caminho, corpo, chave, token=None, **extra):
    return Client().post(f"{URL}{caminho}", json.dumps(corpo), content_type="application/json",
                         HTTP_AUTHORIZATION=f"Bearer {token or c.token}",
                         HTTP_IDEMPOTENCY_KEY=chave, **extra)


def _get(c, caminho, token=None):
    return Client().get(f"{URL}{caminho}", HTTP_AUTHORIZATION=f"Bearer {token or c.token}")


def test_autenticacao_escopo_e_ambiente(c):
    assert Client().get(f"{URL}/estado").status_code == 401
    assert _get(c, "/estado", token="pcpr_test_inventado").status_code == 401
    outro = c.token.replace("pcpr_test_", "pcpr_prod_")
    assert _get(c, "/estado", token=outro).status_code == 401
    estado = _get(c, "/estado").json()
    assert estado["ligada"] and estado["canais"]["whatsapp"] == "ligado"
    assert estado["fluxos"]["diarias_liberadas"] is True
    assert _get(c, "/ferramentas").status_code == 403  # transporte não tem ferramentas


def test_reserva_resultado_entrega_e_idempotencia(c):
    devidas = _get(c, "/comunicacoes/devidas").json()["itens"]
    assert [d["id"] for d in devidas] == [c.com.pk] and devidas[0]["tipo"] == "mensagem_saque"
    chave = f"reserva:{c.com.pk}:v1:exec-0001"
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, chave)
    assert r.status_code == 200, r.content
    reserva = r.json()
    assert reserva["destino"] == f"+{E164}" and reserva["reserva"]["token"]
    assert reserva["mensagem"]["modelo"] == "diarias_teste"
    replay = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, chave)
    assert replay.status_code == 200 and replay.headers["Idempotency-Replayed"] == "true"
    repetida = replay.json()
    assert repetida["id"] == reserva["id"] and repetida["destino"] == reserva["destino"]
    assert repetida["idempotencia_canal"] == reserva["idempotencia_canal"]  # mesma tentativa
    from gestao.automacao.models_api import RegistroIdempotencia
    guardado = RegistroIdempotencia.objects.get(chave=chave).corpo
    assert "destino" not in guardado and "mensagem" not in guardado  # nada sensível no banco
    reserva = repetida  # o token válido é o da resposta mais recente
    # Outra execução (evento + reconciliação ao mesmo tempo) não reserva de novo.
    outra = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:exec-0002")
    assert outra.status_code == 409 and outra.json()["codigo"] == "ja_processada"
    # Mesma chave com outra requisição: 422.
    assert _post(c, f"/comunicacoes/{c.com.pk}/reservar", {"x": 1}, chave).status_code == 422
    corpo = {"reserva_token": reserva["reserva"]["token"], "resultado": "enviada",
             "provedor": "whatsapp", "provedor_mensagem_id": "wamid.N8N1"}
    r = _post(c, f"/comunicacoes/{c.com.pk}/resultado", corpo, f"resultado:{c.com.pk}:1-abc")
    assert r.status_code == 200 and r.json()["estado"] == "enviada"
    errado = {**corpo, "reserva_token": "outro-token-qualquer"}
    assert _post(c, f"/comunicacoes/{c.com.pk}/resultado", errado,
                 f"resultado:{c.com.pk}:2-abc").status_code == 409
    achada = _get(c, "/comunicacoes?provedor_mensagem_id=wamid.N8N1").json()["itens"]
    assert achada == [{"id": c.com.pk, "versao": 1}]
    for status, chave_e in (("lida", "e1"), ("entregue", "e2")):
        r = _post(c, f"/comunicacoes/{c.com.pk}/entrega",
                  {"provedor_mensagem_id": "wamid.N8N1", "status": status,
                   "ocorrido_em": timezone.now().isoformat()},
                  f"entrega:{c.com.pk}:wamid.N8N1:{chave_e}")
        assert r.status_code == 200
    c.com.refresh_from_db()
    assert c.com.situacao == "enviada" and c.com.entrega == "lida"  # não regride
    assert _get(c, f"/comunicacoes/{c.com.pk}").json()["estado"] == "enviada"


def test_desligada_recusa_efeito_novo_mas_aceita_resultado(c):
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:exec-0101")
    token = r.json()["reserva"]["token"]
    chaves.desligar_tudo(c.usuarios["admin"], "incidente")
    chave = f"reserva:{c.com.pk}:v1:exec-0102"
    assert _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, chave).status_code == 423
    # 423 não é guardado: depois de religar, a mesma chave funciona.
    r = _post(c, f"/comunicacoes/{c.com.pk}/resultado",
              {"reserva_token": token, "resultado": "resultado_desconhecido",
               "erro": "timeout ao chamar https://graph.facebook.com/x"},
              f"resultado:{c.com.pk}:desligada")
    assert r.status_code == 200 and r.json()["estado"] == "desconhecido"
    excecao = ExcecaoAutomacao.objects.get(comunicacao=c.com, tipo="resultado_incerto")
    assert "graph.facebook.com" not in excecao.resumo  # mascarado
    assert _post(c, "/excecoes", {"fluxo": "envio", "correlacao_id": "com-1",
                                  "motivo": "limite_tentativas", "detalhe": "x"},
                 "excecao:envio:com-1:limite").status_code == 201


def test_reserva_nao_devida_e_versao(c):
    Comunicacao.objects.filter(pk=c.com.pk).update(
        proxima_tentativa_em=timezone.now() + timedelta(hours=1))
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:exec-0201")
    assert r.status_code == 409 and r.json()["codigo"] == "ainda_nao_devida"
    assert r.json()["disponivel_em"]
    Comunicacao.objects.filter(pk=c.com.pk).update(proxima_tentativa_em=timezone.now())
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:exec-0202",
              HTTP_X_PCPR_VERSAO_ESPERADA="7")
    assert r.status_code == 409 and r.json()["codigo"] == "conflito_de_versao"


def test_sem_modelo_fora_da_janela_nao_sai(c, settings):
    settings.WHATSAPP = {}
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:exec-0301")
    assert r.status_code == 409 and r.json()["codigo"] == "regra_violada"
    assert "modelo aprovado" in r.json()["mensagem"]


def test_worker_interno_nao_envia_com_transporte_n8n(c):
    assert not entrega.processar_uma()
    c.com.refresh_from_db()
    assert c.com.situacao == "agendada"


def test_credencial_revogada_emergencia_e_rotacao(c):
    from gestao.automacao.models_api import CredencialIntegracao
    cred = CredencialIntegracao.objects.get(nome="n8n LAB")
    nova, token_novo = credenciais.rotacionar(c.usuarios["admin"], cred.pk)
    assert _get(c, "/estado", token=token_novo).status_code == 200
    assert _get(c, "/estado").status_code == 200  # a antiga vale durante a carência
    credenciais.emergencia(c.usuarios["admin"], nova.pk)
    assert _get(c, "/estado", token=token_novo).status_code == 401
    credenciais.revogar(c.usuarios["admin"], cred.pk)
    assert _get(c, "/estado").status_code == 401


# ------------------------------------------------------------------ ferramentas e delegação
def _ferramentas_de_teste():
    from gestao.automacao.ferramentas import Campo, Ferramenta, registrar

    registrar(Ferramenta(
        nome="teste.ler_prestacao", descricao="lê", risco="leitura",
        entrada={"ps": Campo("inteiro")}, executar=lambda u, e: {"ps": e["ps"]},
        permitido=lambda u, e: u.has_perm("viagens.view_prestacaoservidor"),
        recurso=lambda e: f"viagens.prestacaoservidor:{e['ps']}"))
    registrar(Ferramenta(
        nome="teste.cancelar_aviso", descricao="cancela um aviso", risco="irreversivel",
        entrada={"comunicacao": Campo("inteiro")},
        executar=lambda u, e: {"cancelada": e["comunicacao"]},
        permitido=lambda u, e: u.has_perm("automacao.operar_automacao")))


def test_ferramenta_exige_delegacao_emitida_pelo_pcpr(c):
    _ferramentas_de_teste()
    admin, op = c.usuarios["admin"], c.usuarios["operador"]
    cred, token = credenciais.emitir(admin, nome="IA", tipo="ia",
                                     ferramentas=["teste.ler_prestacao", "teste.cancelar_aviso"])
    url = "/ferramentas/teste.ler_prestacao/executar"
    corpo = {"ps": c.ps.pk}
    sem = _post(c, url, corpo, "ferramenta:sem-delegacao-01", token=token)
    assert sem.status_code == 403
    # Um cabeçalho inventado (ex.: o id do administrador) não serve: só a delegação do PCPR.
    falso = _post(c, url, corpo, "ferramenta:falso-0000001", token=token,
                  HTTP_X_PCPR_DELEGACAO="dlg_" + "a" * 30)
    assert falso.status_code == 403
    _, dlg = delegacoes.emitir(op, cred, ferramentas=["teste.ler_prestacao"],
                               recurso=f"viagens.prestacaoservidor:{c.ps.pk}", motivo="teste")
    ok = _post(c, url, corpo, "ferramenta:com-delegacao-1", token=token, HTTP_X_PCPR_DELEGACAO=dlg)
    assert ok.status_code == 200 and ok.json()["saida"] == {"ps": c.ps.pk}
    assert ExecucaoFerramenta.objects.get(pk=ok.json()["execucao"]).usuario == op
    de_novo = _post(c, url, corpo, "ferramenta:com-delegacao-2", token=token,
                    HTTP_X_PCPR_DELEGACAO=dlg)
    assert de_novo.status_code == 403  # uso único
    with pytest.raises(delegacoes.DelegacaoNegada):
        delegacoes.emitir(admin, cred, ferramentas=["teste.ler_prestacao"], recurso="",
                          motivo="admin não se delega")


def test_irreversivel_vira_pedido_e_quem_aprova_executa(c):
    _ferramentas_de_teste()
    op = c.usuarios["operador"]
    _, token = credenciais.emitir(op, nome="meu cliente", tipo="pessoal")
    r = _post(c, "/ferramentas/teste.cancelar_aviso/executar", {"comunicacao": 1},
              "ferramenta:irreversivel-01", token=token)
    assert r.status_code == 202 and r.json()["codigo"] == "aprovacao_pendente"
    pedido = PedidoAprovacao.objects.get(pk=r.json()["pedido"])
    ferramentas.aprovar(c.usuarios["gestor"], pedido.pk)
    pedido.refresh_from_db()
    assert pedido.situacao == "aprovado" and pedido.decidido_por == c.usuarios["gestor"]


def test_ferramentas_proibidas_nao_se_registram():
    from gestao.automacao.ferramentas import Ferramenta, registrar

    for nome in ("viagens.escolher_motorista", "prestacao.aprovar", "viagens.emitir_oficio",
                 "diario.lancar_km", "viagens.calcular_diaria"):
        with pytest.raises(ValueError):
            registrar(Ferramenta(nome=nome, descricao="x", risco="preparacao", entrada={},
                                 executar=lambda u, e: {}, permitido=lambda u, e: True))


@override_settings(AUTOMACAO_API_LIGADA=False)
def test_api_desligada_no_preview(c):
    assert _get(c, "/estado").status_code == 404


def test_ferramentas_reais_de_viagens_com_token_pessoal(c):
    op = c.usuarios["operador"]
    _, token = credenciais.emitir(op, nome="cliente do operador", tipo="pessoal")
    nomes = {f["nome"] for f in _get(c, "/ferramentas", token=token).json()["itens"]}
    assert {"prestacao.situacao", "viagens.resumo", "prestacao.lembrar_comprovante"} <= nomes
    r = _post(c, "/ferramentas/prestacao.situacao/executar", {"ps": c.ps.pk},
              "ferramenta:situacao-ps-001", token=token)
    assert r.status_code == 200 and r.json()["saida"]["finalizada"] is False
    assert any("comprovante" in p for p in r.json()["saida"]["pendencias"])
    # Outra unidade: a policy do contexto nega para o usuário efetivo.
    _, alheio = credenciais.emitir(c.usuarios["outra"], nome="outra", tipo="pessoal")
    assert _post(c, "/ferramentas/prestacao.situacao/executar", {"ps": c.ps.pk},
                 "ferramenta:situacao-ps-002", token=alheio).status_code == 403
    assert _post(c, "/ferramentas/prestacao.situacao/executar", {"ps": "x"},
                 "ferramenta:situacao-ps-003", token=token).status_code == 422


def test_telas_de_governanca(c):
    _ferramentas_de_teste()
    admin = Client()
    admin.force_login(c.usuarios["admin"])
    for nome in ("credenciais", "aprovacoes", "execucoes", "links"):
        assert admin.get(f"/automacao/{'historico' if nome == 'execucoes' else nome}/"
                         ).status_code == 200, nome
    r = admin.post("/automacao/credenciais/", {"nome": "n8n novo", "tipo": "transporte",
                                               "dias": "30"})
    import re
    achado = re.search(rb"pcpr_test_[A-Za-z0-9_-]{30,}", r.content)
    assert r.status_code == 200 and achado  # mostrado uma vez
    assert achado.group() not in admin.get("/automacao/credenciais/").content  # só o prefixo
    op = Client()
    op.force_login(c.usuarios["operador"])
    assert op.get("/automacao/historico/").status_code == 403
    assert op.get("/automacao/credenciais/").status_code == 200  # só os pessoais dele


def test_link_pessoal_escopo_validade_e_revogacao(c):
    from django.http import HttpResponse

    from gestao.automacao import links
    from gestao.automacao.models import LinkAcesso

    links.registrar_pagina(links.PaginaDeLink(
        "situacao", "Minha situação", lambda req, link, resto: HttpResponse(f"ok {resto}")))
    link, token = links.criar(escopo="situacao", recurso="teste:1", servidor_id=c.ps.servidor_id)
    assert LinkAcesso.objects.get(pk=link.pk).token_hash != token
    url = f"/p/{token}/"
    assert Client().get(url).content == b"ok "
    assert Client().get(f"/p/{token}/salvar/").content == b"ok salvar"
    assert Client().get(url).headers["X-Robots-Tag"].startswith("noindex")
    _, token2 = links.criar(escopo="situacao", recurso="teste:1", servidor_id=c.ps.servidor_id)
    assert Client().get(url).status_code == 404  # o link novo revogou o anterior
    assert Client().get(f"/p/{token2}/").status_code == 200
    LinkAcesso.objects.filter(token_hash=links._hash(token2)).update(
        expira_em=timezone.now() - timedelta(seconds=1))
    assert Client().get(f"/p/{token2}/").status_code == 404
    assert Client().get("/p/curto/").status_code == 404
    from gestao.automacao.entrega import sem_credencial
    assert token2 not in sem_credencial(f"Abra https://x.invalid/p/{token2}/ agora")


def test_optout_cancela_o_envio_ja_reservado(c):
    """Contato revogado com o envio já reservado pelo n8n: a comunicação é cancelada na hora;
    falha depois não a reagenda; se o n8n já tinha mandado, o resultado é registrado como é e
    abre exceção para uma pessoa conferir."""
    from gestao.automacao import contatos as contatos_mod
    from gestao.automacao.models import ContatoVerificado as CV
    from gestao.automacao.models import ExcecaoAutomacao

    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:optout")
    assert r.status_code == 200, r.content
    token = r.json()["reserva"]["token"]
    contato = CV.objects.get(servidor_id=c.ps.servidor_id)
    contatos_mod.revogar(c.usuarios["operador"], contato.pk, "Saiu do teste")
    c.com.refresh_from_db()
    assert c.com.situacao == "cancelada" and c.com.reservada_ate is None
    falha = _post(c, f"/comunicacoes/{c.com.pk}/resultado",
                  {"reserva_token": token, "resultado": "falha_temporaria",
                   "provedor": "whatsapp", "erro": "503"}, f"resultado:{c.com.pk}:optout-1")
    assert falha.status_code == 200, falha.content
    c.com.refresh_from_db()
    assert c.com.situacao == "cancelada"  # não ressuscita
    assert not ExcecaoAutomacao.objects.filter(chave__startswith="depois-do-cancelamento").exists()


def test_envio_que_saiu_depois_do_optout_vira_excecao(c):
    from gestao.automacao import contatos as contatos_mod
    from gestao.automacao.models import ContatoVerificado as CV
    from gestao.automacao.models import ExcecaoAutomacao

    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:optout2")
    token = r.json()["reserva"]["token"]
    contato = CV.objects.get(servidor_id=c.ps.servidor_id)
    contatos_mod.revogar(c.usuarios["operador"], contato.pk, "Saiu do teste")
    ok = _post(c, f"/comunicacoes/{c.com.pk}/resultado",
               {"reserva_token": token, "resultado": "enviada", "provedor": "whatsapp",
                "provedor_mensagem_id": "wamid.OPTOUT"}, f"resultado:{c.com.pk}:optout-2")
    assert ok.status_code == 200, ok.content
    c.com.refresh_from_db()
    assert c.com.situacao == "enviada" and c.com.mensagem_id == "wamid.OPTOUT"
    assert ExcecaoAutomacao.objects.filter(
        chave=f"depois-do-cancelamento:{c.com.pk}", tipo="contato").exists()


# ------------------------------------------------------------------ 3ª revisão do PR #24 (Codex)
def test_desligada_nao_consome_a_delegacao(c):
    from gestao.automacao.ferramentas import Campo, Ferramenta, registrar

    registrar(Ferramenta(
        nome="teste.cancelar_com_recurso", descricao="cancela", risco="irreversivel",
        entrada={"comunicacao": Campo("inteiro")}, executar=lambda u, e: {},
        permitido=lambda u, e: u.has_perm("automacao.operar_automacao"),
        recurso=lambda e: f"automacao.comunicacao:{e['comunicacao']}"))
    admin, op = c.usuarios["admin"], c.usuarios["operador"]
    cred, token = credenciais.emitir(admin, nome="IA2", tipo="ia",
                                     ferramentas=["teste.cancelar_com_recurso"])
    _, dlg = delegacoes.emitir(op, cred, ferramentas=["teste.cancelar_com_recurso"],
                               recurso="automacao.comunicacao:1", motivo="teste")
    chaves.desligar_tudo(admin, "teste")
    url = "/ferramentas/teste.cancelar_com_recurso/executar"
    r = _post(c, url, {"comunicacao": 1}, "ferramenta:desligada-001", token=token,
              HTTP_X_PCPR_DELEGACAO=dlg)
    assert r.status_code == 423
    chaves.alterar(admin, chaves.GERAL, estado="ligada")
    r = _post(c, url, {"comunicacao": 1}, "ferramenta:desligada-001", token=token,
              HTTP_X_PCPR_DELEGACAO=dlg)
    assert r.status_code == 202  # a delegação não tinha sido gasta pelo 423


def test_sombra_nao_executa_pedido_que_ja_estava_na_fila(c):
    _ferramentas_de_teste()
    op = c.usuarios["operador"]
    _, token = credenciais.emitir(op, nome="meu cliente 2", tipo="pessoal")
    r = _post(c, "/ferramentas/teste.cancelar_aviso/executar", {"comunicacao": 1},
              "ferramenta:sombra-0000001", token=token)
    pedido = PedidoAprovacao.objects.get(pk=r.json()["pedido"])
    chaves.alterar(c.usuarios["admin"], chaves.nome_fluxo("ferramentas"), estado="ligada",
                   modo="sombra")
    with pytest.raises(ferramentas.FerramentaRecusada):
        ferramentas.aprovar(c.usuarios["gestor"], pedido.pk)
    pedido.refresh_from_db()
    assert pedido.situacao == "pendente"


def test_reserva_em_andamento_abandonada_e_assumida(c):
    from datetime import timedelta

    from gestao.automacao.models_api import RegistroIdempotencia

    chave = f"reserva:{c.com.pk}:v1:abandonada"
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, chave)
    assert r.status_code == 200
    # Simula o processo que morreu depois de reservar a chave e antes de gravar a resposta.
    RegistroIdempotencia.objects.filter(chave=chave).update(
        status=0, corpo={}, criado_em=timezone.now() - timedelta(minutes=10))
    de_novo = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, chave)
    # Não fica preso no "em andamento" (409 com Retry-After para sempre): a chamada assume
    # e o serviço responde pelo estado real (a comunicação já está reservada).
    assert "Retry-After" not in de_novo, de_novo.content
    assert RegistroIdempotencia.objects.get(chave=chave).status != 0  # resolvida


def test_total_de_anexos_e_conferido(c):
    from gestao.automacao.models_api import CredencialIntegracao

    cred = CredencialIntegracao.objects.get(pk=credenciais.autenticar(f"Bearer {c.token}").pk)
    cred.escopos = [*cred.escopos, "recebimentos:criar"]
    cred.save(update_fields=["escopos"])
    base = {"canal": "whatsapp", "mensagem_id_canal": "wamid.TOT", "remetente": E164,
            "motivo": "sem_anexo"}
    for extra in ({"anexo_indice": 0}, {"anexo_indice": 0, "total_anexos": 0},
                  {"anexo_indice": 2, "total_anexos": 2}):
        r = _post(c, "/recebimentos/sem-arquivo", {**base, **extra},
                  f"receb:whatsapp:wamid.TOT:{extra['anexo_indice']}")
        assert r.status_code == 422, extra


def test_entrega_exige_hora_e_id_do_provedor_sem_cortar(c):
    r = _post(c, f"/comunicacoes/{c.com.pk}/reservar", {}, f"reserva:{c.com.pk}:v1:r5-0001")
    token = r.json()["reserva"]["token"]
    longo = "wamid." + "x" * 300
    assert _post(c, f"/comunicacoes/{c.com.pk}/resultado",
                 {"reserva_token": token, "resultado": "enviada", "provedor": "whatsapp",
                  "provedor_mensagem_id": longo}, f"resultado:{c.com.pk}:r5-1").status_code == 422
    ok = _post(c, f"/comunicacoes/{c.com.pk}/resultado",
               {"reserva_token": token, "resultado": "enviada", "provedor": "whatsapp",
                "provedor_mensagem_id": "wamid.R5"}, f"resultado:{c.com.pk}:r5-2")
    assert ok.status_code == 200
    sem_hora = _post(c, f"/comunicacoes/{c.com.pk}/entrega",
                     {"provedor_mensagem_id": "wamid.R5", "status": "lida"},
                     f"entrega:{c.com.pk}:wamid.R5:lida")
    assert sem_hora.status_code == 422


def test_pedido_vencido_fica_expirado(c):
    _ferramentas_de_teste()
    op = c.usuarios["operador"]
    _, token = credenciais.emitir(op, nome="meu cliente 3", tipo="pessoal")
    r = _post(c, "/ferramentas/teste.cancelar_aviso/executar", {"comunicacao": 1},
              "ferramenta:vencido-000001", token=token)
    pedido = PedidoAprovacao.objects.get(pk=r.json()["pedido"])
    PedidoAprovacao.objects.filter(pk=pedido.pk).update(
        expira_em=timezone.now() - timedelta(minutes=1))
    with pytest.raises(ferramentas.FerramentaRecusada):
        ferramentas.aprovar(c.usuarios["gestor"], pedido.pk)
    pedido.refresh_from_db()
    assert pedido.situacao == "expirado"


def test_resultado_tardio_nao_troca_o_envio_mais_novo(c):
    """Tentativa 1 incerta; a pessoa tentou de novo e a 2 saiu; depois a 1 também confirma:
    o id do provedor da comunicação continua o da 2 e abre exceção de provável duplicado."""
    from gestao.automacao.models import TentativaEntrega
    from gestao.integracoes.whatsapp.porta import Envio, Origem

    com = c.com
    t1 = TentativaEntrega.objects.create(comunicacao=com, numero=1, chave="t-r5-1",
                                         adaptador="n8n", resultado="incerta")
    t2 = TentativaEntrega.objects.create(comunicacao=com, numero=2, chave="t-r5-2",
                                         adaptador="n8n")
    entrega.registrar_resultado(t2.pk, envio=Envio(mensagem_id="wamid.NOVA",
                                                   origem=Origem.CLOUD_API), origem="n8n")
    entrega.registrar_resultado(t1.pk, envio=Envio(mensagem_id="wamid.VELHA",
                                                   origem=Origem.CLOUD_API), origem="n8n")
    com.refresh_from_db()
    assert com.mensagem_id == "wamid.NOVA"
    assert ExcecaoAutomacao.objects.filter(chave=f"duplicado:{com.pk}:t1").exists()


def test_recebimento_v1_exige_a_hora_da_chegada(c):
    from gestao.automacao.models_api import CredencialIntegracao

    cred = CredencialIntegracao.objects.get(pk=credenciais.autenticar(f"Bearer {c.token}").pk)
    cred.escopos = [*cred.escopos, "recebimentos:criar"]
    cred.save(update_fields=["escopos"])
    r = _post(c, "/recebimentos/sem-arquivo", {
        "canal": "whatsapp", "mensagem_id_canal": "wamid.SEMHORA", "anexo_indice": 0,
        "total_anexos": 1, "remetente": E164, "motivo": "sem_anexo"},
        "receb:whatsapp:wamid.SEMHORA:0")
    assert r.status_code == 422


def test_entrega_confere_a_tentativa_do_callback(c):
    for invalida in ("1", 0, True):
        r = _post(c, f"/comunicacoes/{c.com.pk}/entrega",
                  {"provedor_mensagem_id": "wamid.T", "status": "entregue",
                   "ocorrido_em": timezone.now().isoformat(), "tentativa": invalida},
                  f"entrega:{c.com.pk}:wamid.T:inv-{invalida!r}")
        assert r.status_code == 422, invalida
    Comunicacao.objects.filter(pk=c.com.pk).update(situacao="reservada", tentativas=2,
                                                   mensagem_id="")
    r = _post(c, f"/comunicacoes/{c.com.pk}/entrega",
              {"provedor_mensagem_id": "wamid.T1", "status": "entregue",
               "ocorrido_em": timezone.now().isoformat(), "tentativa": 1},
              f"entrega:{c.com.pk}:wamid.T1:entregue")
    assert r.status_code == 200, r.content
    c.com.refresh_from_db()
    assert c.com.mensagem_id == "" and c.com.situacao == "reservada"  # a 1 não confirma a 2
