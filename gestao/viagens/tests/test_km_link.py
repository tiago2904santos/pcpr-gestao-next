"""Link de km na véspera (fluxo 10-4), de ponta a ponta com o adaptador simulado: rotina da
véspera → comunicação → envio (o link nasce no envio) → página pública → lançamentos do
aparelho (repetidos, em conflito, inválidos) → link revogado no cancelamento e na troca de
motorista → lembrete depois da volta.

O envio ao canal recusa rodar com transação aberta; os testes rodam dentro da transação do
pytest e desligam essa trava (como em `test_whatsapp_prestacao.py`).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit

import pytest
from django.contrib.auth.models import Group
from django.db.models import F
from django.test import Client
from django.utils import timezone
from django.utils.html import escapejs

from gestao.automacao import chaves, contatos, entrega, ganchos, links
from gestao.automacao import comunicacoes as automacao
from gestao.automacao.models import Comunicacao, ContatoVerificado, LinkAcesso
from gestao.identidade.models import Usuario
from gestao.integracoes.whatsapp.adaptadores import AdaptadorSimulado
from gestao.plataforma.models import EventoAuditoria
from gestao.viagens import comunicacoes_viagem as cv
from gestao.viagens import diario as servico_diario
from gestao.viagens import km_link, services
from gestao.viagens.models import (
    DiarioBordo,
    DiarioBordoTrecho,
    Oficio,
    PrestacaoContas,
    Trecho,
    Viajante,
)

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
S = Comunicacao.Situacao
FLUXOS = (cv.FLUXO_KM, cv.FLUXO_LEMBRETES_KM, cv.FLUXO_AVISOS)
URL_LINK = re.compile(r"https?://\S+?/p/[A-Za-z0-9_-]{32,128}/")


class Espiao(AdaptadorSimulado):
    def __init__(self):
        self.envios = []

    def enviar(self, mensagem, simular=""):
        self.envios.append(mensagem)
        return super().enviar(mensagem, simular)


@pytest.fixture(autouse=True)
def _sem_trava_de_transacao(monkeypatch):
    monkeypatch.setattr(entrega, "VERIFICAR_TRANSACAO", False)
    monkeypatch.setattr(cv, "HORA_DO_ENVIO", time(0, 0))  # o envio do dia já é devido
    cv.registrar()  # no app, `ViagensConfig.ready` (gestao/viagens/apps.py)


@pytest.fixture
def c():
    cen = cenario_completo()
    admin = Usuario.objects.create_user("admin-km", "admin-km@pc.pr.gov.br", "x",
                                        nome="Administração da automação")
    admin.groups.add(Group.objects.get(name="ADMINISTRADOR"))
    cen.usuarios["admin"] = admin
    oficio = Oficio.objects.get(pk=cen.ids["oficio_emitido"])
    # A viagem sai amanhã às 09:00 (a rotina da véspera é de hoje).
    primeiro = oficio.trechos.order_by("ordem").first()
    amanha = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=1),
                                                  time(9, 0)))
    delta = amanha - primeiro.saida_em
    Trecho.objects.filter(oficio=oficio).update(saida_em=F("saida_em") + delta,
                                                chegada_em=F("chegada_em") + delta)
    cen.oficio = oficio
    cen.equipe = list(Viajante.objects.filter(oficio=oficio).select_related("servidor")
                      .order_by("ordem", "pk"))
    cen.motorista = next(v.servidor for v in cen.equipe if v.motorista)
    cen.outro = next(v.servidor for v in cen.equipe if not v.motorista)
    for i, v in enumerate(cen.equipe):
        v.servidor.telefone = f"4199999000{i + 1}"
        v.servidor.save(update_fields=["telefone"])
    return cen


def _ligar(c, modo="automatico"):
    admin = c.usuarios["admin"]
    chaves.alterar(admin, chaves.GERAL, estado="ligada")
    chaves.alterar(admin, chaves.nome_canal("whatsapp"), estado="ligada")
    for fluxo in FLUXOS:
        chaves.alterar(admin, chaves.nome_fluxo(fluxo), estado="ligada", modo=modo)


def _contatos(c, *, testadores=True):
    op = c.usuarios["operador"]
    for v in c.equipe:
        contato = contatos.cadastrar(op, v.servidor_id)
        contatos.confirmar_numero(op, contato.pk)
        contatos.registrar_optin(op, contato.pk, ContatoVerificado.OrigemOptin.FORMULARIO)
        if testadores:
            contatos.autorizar_testador(c.usuarios["admin"],
                                        ContatoVerificado.objects.get(pk=contato.pk).endereco,
                                        f"Testador {v.servidor_id}")


def _enviar_link(c) -> tuple[str, Comunicacao, Espiao]:
    _ligar(c)
    _contatos(c)
    cv.agendar_links_km()
    com = Comunicacao.objects.get(tipo=cv.LINK_KM)
    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)
    com.refresh_from_db()
    assert com.situacao == S.ENVIADA, com.motivo
    return urlsplit(URL_LINK.search(espiao.envios[0].texto).group(0)).path, com, espiao


def _diario(c) -> DiarioBordo:
    return DiarioBordo.objects.get(prestacao__oficio=c.oficio)


def _linhas(c) -> list[DiarioBordoTrecho]:
    return list(DiarioBordoTrecho.objects.filter(diario=_diario(c)).order_by("ordem"))


def _postar(cliente: Client, caminho: str, lancamentos: list) -> dict:
    r = cliente.post(caminho + "salvar/", json.dumps({"lancamentos": lancamentos}),
                     content_type="application/json")
    corpo = r.json()
    corpo["_status"] = r.status_code
    return corpo


def _item(ident, linha, campos, base=None):
    return {"id": ident, "linha": linha.pk, "chave": km_link.chave_da_linha(linha),
            "campos": campos, "base": base if base is not None else
            {k: getattr(linha, k) for k in campos}}


# ------------------------------------------------------------------ agendamento e envio
def test_rotina_da_vespera_agenda_um_link_por_diario_e_o_envio_cria_o_link(c):
    path, com, espiao = _enviar_link(c)
    d = _diario(c)
    assert com.servidor_id == c.motorista.pk
    assert com.recurso == f"viagens.diario:{d.pk}"
    assert com.criada_por == c.usuarios["operador"]  # quem emitiu age pelo link
    cv.agendar_links_km()  # rodar de novo não duplica
    assert Comunicacao.objects.filter(tipo=cv.LINK_KM).count() == 1
    assert len(espiao.envios) == 1 and espiao.envios[0].modelo is not None  # fora da janela
    texto = espiao.envios[0].texto
    assert "dados fictícios" in texto and "ABC1D23" not in texto  # sem placa na mensagem
    link = LinkAcesso.objects.get()
    assert (link.escopo, link.recurso, link.servidor_id, link.comunicacao_id) == (
        "km", f"viagens.diario:{d.pk}", c.motorista.pk, com.pk)
    token = path.strip("/").split("/")[-1]
    # A cópia guardada fica com o marcador: o link nasce só na hora do envio.
    assert token not in com.conteudo.texto and ganchos.PLACEHOLDER_LINK in com.conteudo.texto
    assert all(token not in p for p in com.conteudo.parametros)
    assert link.token_hash != token


def test_fora_da_lista_de_testadores_nao_cria_link(c):
    _ligar(c)
    _contatos(c, testadores=False)
    cv.agendar_links_km()
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    com = Comunicacao.objects.get(tipo=cv.LINK_KM)
    assert com.situacao == S.RECUSADA and "testadores" in com.motivo
    assert LinkAcesso.objects.count() == 0 and espiao.envios == []


def test_nova_tentativa_recusada_nao_derruba_o_link_entregue(c):
    path, com, _ = _enviar_link(c)
    # Outro envio do link ao mesmo motorista, que o worker recusa (o telefone do cadastro
    # mudou): não pode criar link nem revogar o que a pessoa já tem.
    c.motorista.telefone = "41988887777"
    c.motorista.save(update_fields=["telefone"])
    de_novo = automacao.agendar(tipo=cv.LINK_KM, servidor_id=c.motorista.pk,
                                recurso=com.recurso, chave="link-km-de-novo",
                                criada_por=c.usuarios["operador"], contexto=com.contexto,
                                versao=com.versao)
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    de_novo.refresh_from_db()
    assert de_novo.situacao == S.RECUSADA and espiao.envios == []
    link = LinkAcesso.objects.get()
    assert link.revogado_em is None and link.comunicacao_id == com.pk
    assert Client().get(path).status_code == 200


def test_em_sombra_nao_cria_link(c):
    _ligar(c, modo="sombra")
    _contatos(c)
    cv.agendar_links_km()
    entrega.processar_uma(porta=Espiao())
    assert Comunicacao.objects.get(tipo=cv.LINK_KM).situacao == S.SOMBRA
    assert not LinkAcesso.objects.exists()


def test_sem_contato_nao_cria_link_e_nada_sai(c):
    _ligar(c)
    cv.agendar_links_km()
    espiao = Espiao()
    entrega.processar_uma(porta=espiao)
    assert Comunicacao.objects.get(tipo=cv.LINK_KM).situacao == S.RECUSADA
    assert not LinkAcesso.objects.exists() and espiao.envios == []


# ------------------------------------------------------------------ página pública
def test_pagina_mostra_so_os_trechos_deste_diario(c):
    path, _, _ = _enviar_link(c)
    r = Client().get(path)
    assert r.status_code == 200
    html = r.content.decode()
    assert r["X-Robots-Tag"].startswith("noindex") and r["Referrer-Policy"] == "no-referrer"
    assert "Arapongas/PR" in html and "Curitiba/PR" in html
    for proibido in ("ABC1D23", "ABC-1D23", "Maringá", "Ofício", c.outro.nome,
                     c.motorista.cpf, c.outro.cpf):
        assert proibido not in html, proibido
    # CSP estrita: nenhum script ou estilo inline; o módulo vem com nonce.
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    assert "style=" not in html and "km-offline.js" in html
    assert len(_linhas(c)) == 2 and html.count("data-km-form") == 2


def test_service_worker_tem_escopo_do_link(c):
    path, _, _ = _enviar_link(c)
    r = Client().get(path + "sw/")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/javascript")
    assert r["Service-Worker-Allowed"] == path
    assert f'const PAGINA = "{escapejs(path)}"' in r.content.decode()


def test_lancamentos_offline_repetidos_gravam_uma_vez(c):
    path, _, _ = _enviar_link(c)
    cliente = Client()
    ida, volta = _linhas(c)
    lote = [_item("aparelho-0001", ida, {"km_inicial": "45.210", "km_final": "45590"}),
            _item("aparelho-0002", volta, {"km_inicial": 45600})]
    primeiro = _postar(cliente, path, lote)
    assert primeiro["_status"] == 200
    assert [r["situacao"] for r in primeiro["resultados"]] == ["gravado", "gravado"]
    trilha = EventoAuditoria.objects.filter(tabela="viagens_diariobordotrecho").count()
    segundo = _postar(cliente, path, lote)  # a resposta se perdeu: o aparelho reenvia
    assert [r["situacao"] for r in segundo["resultados"]] == ["gravado", "gravado"]
    assert EventoAuditoria.objects.filter(tabela="viagens_diariobordotrecho").count() == trilha
    ida.refresh_from_db()
    assert (ida.km_inicial, ida.km_final) == (45210, 45590)
    evento = EventoAuditoria.objects.get(tabela="viagens_diariobordotrecho",
                                         registro_id=str(ida.pk),
                                         requisicao_id=f"km:{ida.diario_id}:aparelho-0001")
    assert evento.usuario_id == c.usuarios["operador"].pk  # em nome de quem enviou o link
    link = LinkAcesso.objects.get()
    assert link.primeiro_lancamento_em and link.ultimo_lancamento_em
    # O setor apaga o km; o mesmo lançamento chegando de novo não volta a gravar.
    servico_diario.salvar_linhas(c.usuarios["operador"], ida.diario_id,
                                 {ida.pk: {"km_inicial": "", "km_final": ""}})
    terceiro = _postar(cliente, path, lote[:1])
    assert terceiro["resultados"][0]["situacao"] == "gravado"
    ida.refresh_from_db()
    assert ida.km_inicial is None and ida.km_final is None


def test_conflito_nao_sobrescreve_e_a_pessoa_escolhe(c):
    path, _, _ = _enviar_link(c)
    cliente = Client()
    _, volta = _linhas(c)
    _postar(cliente, path, [_item("aparelho-0010", volta, {"km_inicial": 45600})])
    # O setor corrige o km depois; o aparelho, offline, ainda via 45.600.
    servico_diario.salvar_linhas(c.usuarios["operador"], volta.diario_id,
                                 {volta.pk: {"km_inicial": "45650"}})
    r = _postar(cliente, path, [_item("aparelho-0011", volta, {"km_inicial": 45700},
                                      base={"km_inicial": 45600})])["resultados"][0]
    assert r["situacao"] == "conflito"
    assert r["servidor"]["km_inicial"] == 45650 and r["seu"]["km_inicial"] == 45700
    volta.refresh_from_db()
    assert volta.km_inicial == 45650
    # "Usar o meu": lançamento novo, com a base no valor do sistema.
    r = _postar(cliente, path, [_item("aparelho-0012", volta, {"km_inicial": 45700},
                                      base={"km_inicial": 45650})])["resultados"][0]
    assert r["situacao"] == "gravado"
    volta.refresh_from_db()
    assert volta.km_inicial == 45700
    # Campo que a pessoa não mexeu (igual à base) não gera conflito com o outro.
    servico_diario.salvar_linhas(c.usuarios["operador"], volta.diario_id,
                                 {volta.pk: {"km_final": "46000"}})
    r = _postar(cliente, path, [_item("aparelho-0013", volta,
                                      {"km_inicial": 45710, "km_final": None},
                                      base={"km_inicial": 45700, "km_final": None})]
                )["resultados"][0]
    assert r["situacao"] == "gravado"


def test_validacoes_do_km(c):
    path, _, _ = _enviar_link(c)
    cliente = Client()
    ida, _ = _linhas(c)
    casos = [
        _item("aparelho-0020", ida, {"km_inicial": 500, "km_final": 400}),
        _item("aparelho-0021", ida, {"km_inicial": "12a"}),
        _item("aparelho-0022", ida, {"km_inicial": "12345678"}),
        _item("aparelho-0023", ida, {"km_inicial": "-5"}),
        _item("aparelho-0024", ida, {"km_inicial": 1000, "km_final": 9000}),
        {**_item("aparelho-0025", ida, {"km_inicial": 10}), "chave": "t:999999"},
        _item("x", ida, {"km_inicial": 10}),
    ]
    resultados = _postar(cliente, path, casos)["resultados"]
    assert [r["situacao"] for r in resultados] == ["recusado"] * len(casos)
    assert "menor" in resultados[0]["mensagem"] and "roteiro" in resultados[5]["mensagem"]
    ida.refresh_from_db()
    assert ida.km_inicial is None and ida.km_final is None
    assert _postar(cliente, path, [{}] * 51)["_status"] == 400
    r = cliente.post(path + "salvar/", "não é json", content_type="application/json")
    assert r.status_code == 400


def test_linha_de_outro_diario_nao_e_alcancada(c):
    path, _, _ = _enviar_link(c)
    # Outro diário, de outro ofício (montado direto: só precisa existir).
    outra = PrestacaoContas.objects.create(oficio_id=c.ids["oficio_rascunho"])
    linha = servico_diario.linhas(servico_diario.obter(outra))[0]
    r = _postar(Client(), path, [_item("aparelho-0030", linha, {"km_inicial": 10})])
    assert r["resultados"][0]["situacao"] == "recusado"
    linha.refresh_from_db()
    assert linha.km_inicial is None


def test_formulario_sem_javascript_grava_e_repetir_nao_duplica(c):
    path, _, _ = _enviar_link(c)
    cliente = Client()
    ida, _ = _linhas(c)
    dados = {"id": "formulario-01", "linha": ida.pk, "chave": km_link.chave_da_linha(ida),
             "km_inicial": "45100", "km_final": "45480", "base_km_inicial": "",
             "base_km_final": ""}
    r = cliente.post(path + "salvar/", dados)
    assert r.status_code == 200 and "Salvo no sistema" in r.content.decode()
    r = cliente.post(path + "salvar/", dados)  # F5 depois do envio
    assert r.status_code == 200
    ida.refresh_from_db()
    assert (ida.km_inicial, ida.km_final) == (45100, 45480)
    # Recusado: a página volta com o motivo e com o que a pessoa digitou.
    r = cliente.post(path + "salvar/", {**dados, "id": "formulario-02", "km_final": "45000",
                                        "base_km_inicial": "45100", "base_km_final": "45480"})
    html = r.content.decode()
    assert r.status_code == 400 and "Não foi salvo" in html and 'value="45000"' in html
    ida.refresh_from_db()
    assert ida.km_final == 45480


def test_csrf_vale_para_o_envio_do_aparelho(c):
    path, _, _ = _enviar_link(c)
    cliente = Client(enforce_csrf_checks=True)
    assert cliente.get(path).status_code == 200
    ida, _ = _linhas(c)
    corpo = json.dumps({"lancamentos": [_item("aparelho-0040", ida, {"km_inicial": 1})]})
    sem = cliente.post(path + "salvar/", corpo, content_type="application/json")
    assert sem.status_code == 403
    token = cliente.cookies["pcpr_csrf"].value
    com = cliente.post(path + "salvar/", corpo, content_type="application/json",
                       HTTP_X_CSRFTOKEN=token)
    assert com.status_code == 200 and com.json()["resultados"][0]["situacao"] == "gravado"


# ------------------------------------------------------------------ link que não vale
def test_cancelar_o_oficio_revoga_o_link(c):
    path, _, _ = _enviar_link(c)
    services.cancelar(c.oficio, c.usuarios["gestor"], "Evento adiado (teste).")
    link = LinkAcesso.objects.get()
    assert link.revogado_em and link.motivo_revogacao == LinkAcesso.Motivo.OFICIO_CANCELADO
    r = Client().get(path)
    assert r.status_code == 404 and "Link indisponível" in r.content.decode()
    r = Client().post(path + "salvar/", json.dumps({"lancamentos": []}),
                      content_type="application/json")
    assert r.status_code == 404


def test_vencido_de_outro_escopo_ou_de_outra_pessoa_da_a_mesma_pagina(c):
    path, _, _ = _enviar_link(c)
    d = _diario(c)
    link = LinkAcesso.objects.get()

    def indisponivel(caminho):
        r = Client().get(caminho)
        return r.status_code == 404 and "Link indisponível" in r.content.decode()

    LinkAcesso.objects.filter(pk=link.pk).update(expira_em=timezone.now() - timedelta(seconds=1))
    assert indisponivel(path)
    # Link de km de quem não é o responsável pelo diário.
    _, token = links.criar(escopo="km", recurso=km_link.recurso(d.pk), servidor_id=c.outro.pk)
    assert indisponivel(f"/p/{token}/")
    # Link de km apontando para outra coisa que não um diário.
    _, token = links.criar(escopo="km", recurso="viagens.prestacaoservidor:1",
                           servidor_id=c.motorista.pk)
    assert indisponivel(f"/p/{token}/")
    # Outro escopo (sem página registrada) para o mesmo diário.
    livres = [e for e in LinkAcesso.Escopo.values if e != "km" and links.pagina(e) is None]
    if livres:
        _, token = links.criar(escopo=livres[0], recurso=km_link.recurso(d.pk),
                               servidor_id=c.motorista.pk)
        assert indisponivel(f"/p/{token}/")
    assert indisponivel("/p/" + "A" * 43 + "/")
    # Ação desconhecida dentro de um link válido.
    _, token = links.criar(escopo="km", recurso=km_link.recurso(d.pk),
                           servidor_id=c.motorista.pk)
    assert indisponivel(f"/p/{token}/outra-coisa/")


def test_troca_de_motorista_revoga_e_agenda_para_o_novo(c):
    path, _, _ = _enviar_link(c)
    d = _diario(c)
    servico_diario.trocar_motorista_e_viatura(
        c.usuarios["operador"], d.pk, motorista_modo=DiarioBordo.Motorista.SERVIDOR,
        motorista_servidor_id=c.outro.pk, viatura_modo=DiarioBordo.ViaturaModo.OFICIO)
    antigo = LinkAcesso.objects.get()
    assert antigo.motivo_revogacao == LinkAcesso.Motivo.RESPONSAVEL_TROCADO
    assert Client().get(path).status_code == 404
    novo = Comunicacao.objects.get(tipo=cv.LINK_KM, servidor_id=c.outro.pk)
    assert novo.situacao == S.AGENDADA and novo.criada_por == c.usuarios["operador"]
    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)
    novo.refresh_from_db()
    assert novo.situacao == S.ENVIADA, novo.motivo
    caminho = urlsplit(URL_LINK.search(espiao.envios[0].texto).group(0)).path
    assert Client().get(caminho).status_code == 200


# ------------------------------------------------------------------ lembrete
def test_lembrete_depois_da_volta_e_obsoleto_quando_completa(c):
    path, _, _ = _enviar_link(c)
    chegada = timezone.localtime(max(t.chegada_em for t in c.oficio.trechos.all())).date()
    assert cv.agendar_lembretes_km(chegada + timedelta(days=1)) == 1
    lembrete = Comunicacao.objects.get(tipo=cv.LEMBRETE_KM)
    Comunicacao.objects.filter(pk=lembrete.pk).update(proxima_tentativa_em=timezone.now())
    espiao = Espiao()
    assert entrega.processar_uma(porta=espiao)
    lembrete.refresh_from_db()
    assert lembrete.situacao == S.ENVIADA, lembrete.motivo
    assert "2 de 2 trechos" in espiao.envios[0].texto
    assert not URL_LINK.search(espiao.envios[0].texto)  # sem link novo: não derruba o antigo
    assert LinkAcesso.objects.filter(revogado_em__isnull=True).count() == 1
    # Completo pelo link: o lembrete seguinte (outra rodada) fica obsoleto no envio.
    ida, volta = _linhas(c)
    _postar(Client(), path, [_item("aparelho-0050", ida, {"km_inicial": 100, "km_final": 400}),
                             _item("aparelho-0051", volta, {"km_inicial": 400,
                                                            "km_final": 700})])
    outro = automacao.agendar(tipo=cv.LEMBRETE_KM, servidor_id=c.motorista.pk,
                              recurso=km_link.recurso(ida.diario_id), chave="lembrete-2",
                              criada_por=c.usuarios["operador"],
                              contexto={"diario": ida.diario_id, "servidor": c.motorista.pk})
    entrega.processar_uma(porta=Espiao())
    outro.refresh_from_db()
    assert outro.situacao == S.OBSOLETA and "completos" in outro.motivo


def test_service_worker_leva_o_vencimento_do_link(c):
    path, _, _ = _enviar_link(c)
    corpo = Client().get(path + "sw/").content.decode()
    assert "const EXPIRA = " in corpo and "const EXPIRA = 0;" not in corpo
    assert "pcpr-km-pagina:" in corpo and "status: 410" in corpo
