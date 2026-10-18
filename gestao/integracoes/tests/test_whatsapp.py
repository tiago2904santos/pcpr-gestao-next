"""Porta do WhatsApp (Cloud API) sem rede: configuração, webhook (assinatura, verificação,
leitura tolerante e maliciosa) e o adaptador real exercitado com respostas gravadas —
inclusive a classificação dos erros pelo `code` e o que é resultado desconhecido."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from django.test import override_settings

from gestao.integracoes.whatsapp import config, erros, webhook
from gestao.integracoes.whatsapp.adaptadores import (
    AdaptadorCloudApi,
    AdaptadorSimulado,
    classificar,
    conferir_sha256,
)
from gestao.integracoes.whatsapp.porta import Anexo, MensagemSaida, ModeloSaida
from gestao.integracoes.whatsapp.transporte import (
    NaoEnviado,
    Resposta,
    TalvezEnviado,
    TransporteGravado,
)

REAL = config.Configuracao(modo=config.CLOUD_API, phone_number_id="111", access_token="tok",
                           app_secret="seg", verify_token="ver")
PDF = b"%PDF-1.4 teste"


def _ok(wamid="wamid.HBgL1", wa_id="5541999990001"):
    return Resposta(200, json.dumps({"messaging_product": "whatsapp",
                                     "contacts": [{"input": "+5541999990001", "wa_id": wa_id}],
                                     "messages": [{"id": wamid}]}).encode())


def _erro(code, status=400):
    return Resposta(status, json.dumps({"error": {"message": "x", "code": code,
                                                  "error_data": {"details": "d"}}}).encode())


MSG = MensagemSaida(para="5541999990001", texto="Olá (teste)", referencia="com:1:t1")


# ------------------------------------------------------------------ configuração
def test_padrao_e_simulado_e_nao_mostra_segredo():
    c = config.carregar()
    assert c.modo == config.SIMULADO and not c.real
    assert "tok" not in repr(REAL) and "seg" not in repr(REAL)


@override_settings(APP_ENV="preview", WHATSAPP={**{"modo": "cloud_api"}, "phone_number_id": "1",
                                                 "access_token": "t", "app_secret": "s",
                                                 "verify_token": "v"})
def test_preview_nunca_usa_a_cloud_api():
    c = config.carregar()
    assert c.bloqueado_no_ambiente and not c.real
    with pytest.raises(erros.ConfiguracaoIncompleta):
        AdaptadorCloudApi(c)


@override_settings(WHATSAPP={"lista_fechada": "false"})
def test_lista_fechada_so_desliga_em_producao():
    assert config.carregar().lista_fechada is True
    with override_settings(APP_ENV="production"):
        assert config.carregar().lista_fechada is False


@override_settings(WHATSAPP={"modelos": "viagens.diarias_liberadas=diarias_teste:pt_BR;x="})
def test_modelos_da_variavel():
    c = config.carregar()
    assert c.modelo_de("viagens.diarias_liberadas") == config.Modelo("diarias_teste", "pt_BR")
    assert c.modelo_de("x") is None


def test_mascarar_telefone():
    assert config.mascarar_telefone("5541999990001") == "+55 •• ••••-0001"


# ------------------------------------------------------------------ webhook
def test_assinatura_do_corpo_bruto():
    corpo = b'{"object":"whatsapp_business_account"}'
    cab = webhook.assinar(corpo, "seg")
    assert webhook.assinatura_valida(corpo, cab, "seg")
    assert not webhook.assinatura_valida(corpo + b" ", cab, "seg")
    assert not webhook.assinatura_valida(corpo, cab, "outro")
    assert not webhook.assinatura_valida(corpo, None, "seg")
    assert not webhook.assinatura_valida(corpo, "sha1=" + "0" * 64, "seg")
    assert not webhook.assinatura_valida(corpo, cab, "")


def test_desafio_da_inscricao():
    ok = {"hub.mode": "subscribe", "hub.verify_token": "ver", "hub.challenge": "123"}
    assert webhook.desafio(ok, "ver") == "123"
    assert webhook.desafio({**ok, "hub.verify_token": "x"}, "ver") is None
    assert webhook.desafio({**ok, "hub.mode": "unsubscribe"}, "ver") is None
    assert webhook.desafio(ok, "") is None
    assert webhook.desafio({**ok, "hub.challenge": "<script>alert(1)</script>"}, "ver") is None
    assert webhook.desafio({**ok, "hub.challenge": "<script>\n"}, "ver") is None


def test_leitura_de_status_e_mensagem():
    corpo = webhook.montar_status(mensagem_id="wamid.A", status="delivered",
                                  destinatario="5541999990001", referencia="com:7:t1")
    lote = webhook.ler(corpo)
    assert len(lote.status) == 1
    s = lote.status[0]
    assert (s.mensagem_id, s.status, s.referencia) == ("wamid.A", "delivered", "com:7:t1")
    assert s.preco and s.preco.categoria == "service"
    anexo = Anexo(midia_id="M1", tipo="document", mime="application/pdf", sha256="x",
                  nome="c.pdf")
    lote = webhook.ler(webhook.montar_mensagem(mensagem_id="wamid.B", remetente="5541999990001",
                                               anexo=anexo, em_resposta_a="wamid.A",
                                               nome_perfil="Ana", remetente_usuario="BR.abc"))
    m = lote.mensagens[0]
    assert m.tipo == "document" and m.anexo.midia_id == "M1" and m.em_resposta_a == "wamid.A"
    assert m.nome_perfil == "Ana" and m.remetente_usuario == "BR.abc"


@pytest.mark.parametrize("corpo", [b"nao e json", b"[]", b'{"object":"page"}',
                                   b"\xff\xfe", b"{" * 10])
def test_corpo_malformado_ou_de_outro_objeto(corpo):
    with pytest.raises(erros.PayloadInvalido):
        webhook.ler(corpo)


def test_corpo_grande_e_itens_demais():
    with pytest.raises(erros.PayloadInvalido):
        webhook.ler(b" " * (webhook.TAMANHO_MAXIMO + 1))
    muitos = {"object": "whatsapp_business_account", "entry": [{"changes": [{
        "field": "messages", "value": {"statuses": [
            {"id": f"w{i}", "status": "sent"} for i in range(1001)]}}]}]}
    with pytest.raises(erros.PayloadInvalido):
        webhook.ler(json.dumps(muitos).encode())


def test_campos_estranhos_sao_ignorados_sem_quebrar():
    corpo = {"object": "whatsapp_business_account", "entry": [
        "lixo", {"changes": [{"field": "account_update", "value": {}},
                             {"field": "messages", "value": {
                                 "statuses": [{"status": "sent"}, {"id": {"x": 1},
                                                                   "status": "read"}],
                                 "messages": [{"id": "w1", "type": "location",
                                               "timestamp": "nao-numero"},
                                              {"type": "text"}],
                                 "contacts": "lixo"}}]}]}
    lote = webhook.ler(json.dumps(corpo).encode())
    assert lote.ignorados == 4 and len(lote.mensagens) == 1
    assert lote.mensagens[0].tipo == "outro" and lote.mensagens[0].recebida_em is None


# ------------------------------------------------------------------ adaptador Cloud API
def test_envio_de_texto_com_referencia_e_prova():
    t = TransporteGravado([_ok(wa_id="554199990001")])
    envio = AdaptadorCloudApi(REAL, t).enviar(MSG)
    assert envio.mensagem_id == "wamid.HBgL1" and envio.wa_id == "554199990001"
    metodo, url, cab, corpo = t.chamadas[0]
    assert metodo == "POST" and url.startswith("https://graph.facebook.com/v25.0/111/messages?")
    assert "appsecret_proof=" in url and cab["Authorization"] == "Bearer tok"
    dados = json.loads(corpo)
    assert dados["to"] == "+5541999990001" and dados["type"] == "text"
    assert dados["biz_opaque_callback_data"] == "com:1:t1"


def test_envio_de_modelo():
    t = TransporteGravado([_ok()])
    msg = MensagemSaida(para="5541999990001", texto="x", referencia="r",
                        modelo=ModeloSaida("aviso_teste", "pt_BR", ("Ana", "12/2026")),
                        responder_a="wamid.0")
    AdaptadorCloudApi(REAL, t).enviar(msg)
    dados = json.loads(t.chamadas[0][3])
    assert dados["type"] == "template" and dados["template"]["name"] == "aviso_teste"
    assert [p["text"] for p in dados["template"]["components"][0]["parameters"]] == [
        "Ana", "12/2026"]
    assert dados["context"] == {"message_id": "wamid.0"}


@pytest.mark.parametrize("code,tipo", [
    (130429, erros.FalhaTemporaria), (131056, erros.FalhaTemporaria),
    (2, erros.FalhaTemporaria), (131026, erros.FalhaDefinitiva),
    (131047, erros.FalhaDefinitiva), (132001, erros.FalhaDefinitiva),
    (190, erros.CanalBloqueado), (368, erros.CanalBloqueado), (131042, erros.CanalBloqueado),
    (250, erros.CanalBloqueado)])
def test_erros_classificados_pelo_code(code, tipo):
    t = TransporteGravado([_erro(code)])
    with pytest.raises(tipo) as e:
        AdaptadorCloudApi(REAL, t).enviar(MSG)
    assert e.value.codigo == str(code)


def test_o_que_e_resultado_desconhecido():
    assert isinstance(classificar(502, {}), erros.ResultadoIncerto)
    assert isinstance(classificar(400, {}), erros.FalhaDefinitiva)
    with pytest.raises(erros.ResultadoIncerto):
        AdaptadorCloudApi(REAL, TransporteGravado([TalvezEnviado("timeout")])).enviar(MSG)
    with pytest.raises(erros.FalhaTemporaria):  # nem saiu: seguro tentar de novo
        AdaptadorCloudApi(REAL, TransporteGravado([NaoEnviado("dns")])).enviar(MSG)
    with pytest.raises(erros.ResultadoIncerto):  # 200 sem id: não dá para saber
        AdaptadorCloudApi(REAL, TransporteGravado([Resposta(200, b"{}")])).enviar(MSG)


def _midia(url="https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=1",
           conteudo=PDF, tamanho=None):
    sha = base64.b64encode(hashlib.sha256(conteudo).digest()).decode()
    meta = {"url": url, "mime_type": "application/pdf", "sha256": sha,
            "file_size": str(tamanho if tamanho is not None else len(conteudo)), "id": "M1"}
    return Resposta(200, json.dumps(meta).encode()), Resposta(200, conteudo)


def test_download_de_midia_confere_hash_e_tipo():
    meta, arquivo = _midia()
    t = TransporteGravado([meta, arquivo])
    baixada = AdaptadorCloudApi(REAL, t).baixar_midia(Anexo("M1", "document"), 10 * 2**20)
    assert baixada.mime == "application/pdf" and baixada.conteudo == PDF
    assert t.chamadas[1][2]["Authorization"] == "Bearer tok"


def test_download_recusa_host_fora_da_meta_sem_mandar_o_token():
    meta, arquivo = _midia(url="https://atacante.example/arquivo")
    t = TransporteGravado([meta, arquivo])
    with pytest.raises(erros.MidiaInvalida):
        AdaptadorCloudApi(REAL, t).baixar_midia(Anexo("M1", "document"), 10 * 2**20)
    assert len(t.chamadas) == 1  # o Bearer não foi para o outro endereço


def test_download_grande_corrompido_ou_de_outro_tipo():
    meta, _ = _midia(tamanho=11 * 2**20)
    with pytest.raises(erros.MidiaInvalida):
        AdaptadorCloudApi(REAL, TransporteGravado([meta])).baixar_midia(
            Anexo("M1", "document"), 10 * 2**20)
    meta, arquivo = _midia(conteudo=b"MZ executavel")
    with pytest.raises(erros.MidiaInvalida):
        AdaptadorCloudApi(REAL, TransporteGravado([meta, arquivo])).baixar_midia(
            Anexo("M1", "document"), 10 * 2**20)
    meta, _ = _midia()
    adulterado = Resposta(200, PDF + b"x")
    with pytest.raises(erros.MidiaInvalida):
        AdaptadorCloudApi(REAL, TransporteGravado([meta, adulterado])).baixar_midia(
            Anexo("M1", "document"), 10 * 2**20)
    with pytest.raises(erros.MidiaInvalida):
        AdaptadorCloudApi(REAL, TransporteGravado([])).baixar_midia(
            Anexo("../../etc", "document"), 10 * 2**20)


def test_url_vencida_pede_outra_uma_vez():
    meta, arquivo = _midia()
    t = TransporteGravado([meta, Resposta(404, b""), meta, arquivo])
    assert AdaptadorCloudApi(REAL, t).baixar_midia(Anexo("M1", "document"), 2**20).conteudo == PDF


def test_sha256_em_hex_ou_base64():
    hexa = hashlib.sha256(PDF).hexdigest()
    assert conferir_sha256(PDF, hexa) == hexa
    assert conferir_sha256(PDF, base64.b64encode(hashlib.sha256(PDF).digest()).decode()) == hexa
    with pytest.raises(erros.MidiaInvalida):
        conferir_sha256(PDF, "0" * 64)


def test_simulado_e_deterministico_e_ensaia_falhas():
    s = AdaptadorSimulado()
    assert s.enviar(MSG).mensagem_id == s.enviar(MSG).mensagem_id
    for simular, tipo in (("temporaria", erros.FalhaTemporaria),
                          ("definitiva", erros.FalhaDefinitiva),
                          ("incerta", erros.ResultadoIncerto)):
        with pytest.raises(tipo):
            s.enviar(MSG, simular=simular)
    with pytest.raises(erros.FalhaDefinitiva):
        s.enviar(MensagemSaida(para="123", texto="x", referencia="r"))


def test_mudanca_de_outro_numero_e_ignorada():
    corpo = webhook.montar_status(mensagem_id="wamid.A", status="sent", destinatario="5541",
                                  phone_number_id="999")
    assert webhook.ler(corpo, numero_esperado="111").status == ()
    assert len(webhook.ler(corpo, numero_esperado="999").status) == 1


def test_teto_de_itens_conta_tambem_os_malformados():
    """Itens malformados também contam para o teto, conferido a cada item: um corpo assinado
    cheio de lixo não é processado até o fim."""
    lixo = {"object": "whatsapp_business_account", "entry": [{"changes": [{
        "field": "messages", "value": {"statuses": [{"x": i} for i in range(1001)]}}]}]}
    with pytest.raises(erros.PayloadInvalido):
        webhook.ler(json.dumps(lixo).encode())


def test_documento_sem_id_de_midia_e_ignorado():
    corpo = {"object": "whatsapp_business_account", "entry": [{"changes": [{
        "field": "messages", "value": {"messages": [
            {"id": "wamid.SEMMIDIA", "from": "5541999990001", "type": "document",
             "document": {"filename": "x.pdf"}}]}}]}]}
    lote = webhook.ler(json.dumps(corpo).encode())
    assert lote.mensagens == () and lote.ignorados == 1
