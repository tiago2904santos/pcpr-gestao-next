"""eProtocolo: configuração, travas e adaptadores — sem tocar a rede.

O adaptador HTTP recebe um transporte falso que grava as chamadas; assim o contrato com a
documentação oficial (Basic no token, escopo, Bearer + consumerId, caminho de consulta) é
provado sem credencial real.
"""

from __future__ import annotations

import base64
import json
import urllib.parse

import pytest
from django.core.management import call_command

from gestao.integracoes.eprotocolo import config as cfg
from gestao.integracoes.eprotocolo import servico
from gestao.integracoes.eprotocolo.adaptadores import AdaptadorHttp, AdaptadorSimulado
from gestao.integracoes.eprotocolo.erros import (
    ConfiguracaoIncompleta,
    EscritaBloqueada,
    Indisponivel,
    NaoEncontrado,
    Recusado,
)
from gestao.integracoes.eprotocolo.porta import Origem, PedidoDeAbertura

CREDENCIAIS = {"client_id": "id-falso-de-teste-0000", "client_secret": "segredo!",
               "consumer_id": "consumidor-pcpr"}


class TransporteFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, metodo, url, cabecalhos, corpo, timeout):
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": cabecalhos,
                              "corpo": corpo, "timeout": timeout})
        status, dados = self.respostas.pop(0)
        return status, json.dumps(dados).encode()


TOKEN_OK = (200, {"access_token": "jwt-de-teste", "expires_in": 300})


def _config(**extra) -> cfg.Configuracao:
    return cfg.Configuracao(**{"ambiente": cfg.TREINAMENTO, **CREDENCIAIS, **extra})


class TestConfiguracao:
    def test_sem_nada_e_simulado(self, settings):
        settings.EPROTOCOLO = {}
        c = cfg.carregar()
        assert c.ambiente == cfg.SIMULADO and not c.real and not c.oficial
        assert isinstance(servico.adaptador(), AdaptadorSimulado)

    def test_ambiente_real_sem_credencial_continua_simulado(self, settings):
        settings.EPROTOCOLO = {"ambiente": "producao"}
        c = cfg.carregar()
        assert not c.real and "credenciais ausentes" in c.descricao()
        assert isinstance(servico.adaptador(), AdaptadorSimulado)

    def test_urls_oficiais_por_ambiente(self):
        base, token = _config().urls()
        assert base.endswith("/seap/spi-servicos/api-tre")
        assert token.startswith("https://auth-cs-hml.identidadedigital.pr.gov.br/")
        base, token = _config(ambiente=cfg.PRODUCAO).urls()
        assert base == "https://apigateway.paas.pr.gov.br/seap/spi-servicos/api"

    def test_so_producao_real_e_oficial_e_trava_ligada_por_padrao(self):
        assert not _config().oficial
        assert _config(ambiente=cfg.PRODUCAO).oficial
        assert _config().somente_leitura and not _config().escrita_liberada

    def test_mascara_e_nao_vaza_segredo(self, settings):
        settings.EPROTOCOLO = {"ambiente": "treinamento", **CREDENCIAIS}
        d = servico.diagnostico()
        texto = json.dumps(d)
        assert "segredo!" not in texto and CREDENCIAIS["client_id"] not in texto
        assert d["client_id"].startswith("id-f") and d["client_secret"] == "configurado"


class TestSimulado:
    def test_numero_no_formato_idempotente_e_marcado(self):
        a = AdaptadorSimulado()
        p = PedidoDeAbertura(resumo="Ofício 12/2026", interessado="ASCOM", chave="oficio:12")
        um, dois = a.abrir(p), a.abrir(p)
        assert um == dois and len(um.numero) == 9 and um.numero.isdigit()
        assert um.origem == Origem.SIMULADO
        assert not servico.origem_vale_como_oficial(um.origem)

    def test_consulta_simulada_avisa(self):
        s = AdaptadorSimulado().consultar("12.345.678-9")
        assert s.numero == "123456789" and s.origem == Origem.SIMULADO
        with pytest.raises(NaoEncontrado):
            AdaptadorSimulado().consultar("123")


class TestHttp:
    def test_token_segue_a_documentacao_oficial_e_consulta(self):
        t = TransporteFalso([TOKEN_OK, (200, {
            "situacao": "Em trâmite", "localAtual": "PCPR/ASCOM",
            "movimentacoes": [{"data": "2026-10-01T10:00:00", "descricao": "Autuado"}]})])
        s = AdaptadorHttp(_config(), transporte=t).consultar("12.345.678-9")
        token, consulta = t.chamadas
        basic = base64.b64decode(token["cabecalhos"]["Authorization"].split()[1]).decode()
        assert basic == f"{CREDENCIAIS['client_id']}:{CREDENCIAIS['client_secret']}"
        corpo = urllib.parse.parse_qs(token["corpo"].decode())
        assert corpo == {"grant_type": ["client_credentials"],
                         "scope": ["spiserv.protocolos.consultar"]}
        assert consulta["url"].endswith("/api-tre/v3/protocolos/123456789")
        assert consulta["cabecalhos"]["Authorization"] == "Bearer jwt-de-teste"
        assert consulta["cabecalhos"]["consumerId"] == "consumidor-pcpr"
        assert s.situacao == "Em trâmite" and s.ultima.descricao == "Autuado"
        assert s.origem == Origem.TREINAMENTO  # treinamento nunca é oficial

    def test_token_e_reaproveitado_ate_vencer(self):
        agora = [0.0]
        t = TransporteFalso([TOKEN_OK, (200, {}), (200, {}), TOKEN_OK, (200, {})])
        a = AdaptadorHttp(_config(), transporte=t, relogio=lambda: agora[0])
        a.consultar("123456789")
        a.consultar("123456789")
        agora[0] = 10_000
        a.consultar("123456789")
        assert [c["url"].split("/")[-1] for c in t.chamadas].count("jwt") == 2

    def test_erros_viram_mensagens_que_dizem_o_que_fazer(self):
        with pytest.raises(Recusado, match="credenciais"):
            AdaptadorHttp(_config(), transporte=TransporteFalso([(401, {})])).autenticar()
        with pytest.raises(NaoEncontrado):
            AdaptadorHttp(_config(), transporte=TransporteFalso([TOKEN_OK, (404, {})])
                          ).consultar("123456789")
        with pytest.raises(Indisponivel):
            AdaptadorHttp(_config(), transporte=TransporteFalso([TOKEN_OK, (503, {})])
                          ).consultar("123456789")
        with pytest.raises(ConfiguracaoIncompleta):
            AdaptadorHttp(cfg.Configuracao(ambiente=cfg.TREINAMENTO))

    def test_so_https_e_sem_redirecionar(self):
        with pytest.raises(ConfiguracaoIncompleta, match="https"):
            AdaptadorHttp(_config(base_url="http://exemplo.invalido/api"))
        from gestao.integracoes.eprotocolo.adaptadores import transporte_urllib
        with pytest.raises(ConfiguracaoIncompleta, match="HTTPS"):
            transporte_urllib("GET", "http://exemplo.invalido/", {}, None, 1)

    def test_abrir_exige_trava_aberta_e_codigos(self):
        pedido = PedidoDeAbertura(resumo="x", interessado="y", chave="k")
        with pytest.raises(EscritaBloqueada):
            AdaptadorHttp(_config(), transporte=TransporteFalso([])).abrir(pedido)
        with pytest.raises(ConfiguracaoIncompleta, match="códigos institucionais"):
            AdaptadorHttp(_config(somente_leitura=False), transporte=TransporteFalso([])
                          ).abrir(pedido)


def test_comando_de_diagnostico_nao_toca_a_rede(settings, capsys):
    settings.EPROTOCOLO = {}
    call_command("eprotocolo_check")
    saida = capsys.readouterr().out
    assert "Modo simulado" in saida and "somente_leitura" in saida
