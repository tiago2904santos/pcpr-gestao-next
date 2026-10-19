"""Aba Pendências da Agenda: a aba ao lado do Calendário, cada seção só com o que a pessoa
vê nas telas de origem (unidade e permissões), os envios manuais levando à conferência,
rascunhos, prestação vencida ou vencendo, solicitações de evento, exceções da automação,
o estado vazio, a falha isolada de uma seção e o orçamento de consultas."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.automacao import excecoes
from gestao.cadastros.models import Lotacao, Unidade
from gestao.identidade.models import Usuario
from gestao.plataforma import pendencias, rotinas
from gestao.plataforma.navegacao import navegacao_para
from gestao.viagens import envios_manuais, prestacao, services
from gestao.viagens.models import PrestacaoServidor
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db
URL = "/agenda/pendencias/"


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


def _secoes(usuario) -> dict[str, pendencias.Montada]:
    return {m.secao.slug: m for m in pendencias.montar(usuario, timezone.localdate())}


def _grupo(montada: pendencias.Montada, chave: str) -> pendencias.Grupo | None:
    return next((g for g in montada.grupos if g.chave == chave), None)


def _chaves(grupo) -> list[str]:
    return [i.chave for i in grupo.itens] if grupo else []


def _liberar(c, ps: PrestacaoServidor, prazo):
    return prestacao.salvar_solicitacao(c.usuarios["operador"], ps.pk, numero="2026/0001",
                                        liberacao=timezone.localdate(), prazo=prazo)


def test_aba_ao_lado_do_calendario(c, rf):
    pedido = rf.get(URL)
    pedido.user = c.usuarios["operador"]
    agenda = next(m for m in navegacao_para(pedido)["modulos"] if m["chave"] == "agenda")
    itens = [i["rotulo"] for g in agenda["grupos"] for i in g["itens"]]
    assert itens == ["Calendário", "Pendências"]
    ativo = [i["rotulo"] for g in agenda["grupos"] for i in g["itens"] if i["ativo"]]
    assert ativo == ["Pendências"]
    resposta = _cliente(c.usuarios["operador"]).get(URL)
    assert resposta.status_code == 200
    assert b"Pend\xc3\xaancias" in resposta.content


def test_menu_de_viagens_nao_tem_mais_envios_manuais(c, rf):
    pedido = rf.get("/viagens/")
    pedido.user = c.usuarios["operador"]
    viagens = next(m for m in navegacao_para(pedido)["modulos"] if m["chave"] == "viagens")
    assert "Envios manuais" not in [i["rotulo"] for g in viagens["grupos"] for i in g["itens"]]


def test_rascunhos_so_da_unidade_e_so_para_quem_termina(c):
    ascom = _grupo(_secoes(c.usuarios["operador"])["documentos"], "oficios")
    assert set(_chaves(ascom)) == {f"oficio-{c.ids['oficio_rascunho']}",
                                   f"oficio-{c.ids['oficio_vazio']}"}
    # O que sai antes vem primeiro (o rascunho sai em 3 dias); o sem data, depois.
    assert _chaves(ascom)[0] == f"oficio-{c.ids['oficio_rascunho']}"
    assert ascom.itens[0].selo == "Sai em 3 dias" and ascom.itens[0].tom == "aviso"
    assert ascom.itens[0].url == reverse("viagens:editar", args=[c.ids["oficio_rascunho"]])
    dpc = _grupo(_secoes(c.usuarios["outra"])["documentos"], "oficios")
    assert _chaves(dpc) == [f"oficio-{c.ids['oficio_outra_unidade']}"]
    # Quem só consulta não termina documento: a seção nem aparece.
    assert "documentos" not in _secoes(c.usuarios["consulta"])
    # O gestor vê todas as unidades e a unidade de cada um.
    gestor = _grupo(_secoes(c.usuarios["gestor"])["documentos"], "oficios")
    assert f"oficio-{c.ids['oficio_outra_unidade']}" in _chaves(gestor)
    assert any(icone == "building-2" for i in gestor.itens for icone, _ in i.fatos)


def test_os_nao_gerada_aparece_e_some_quando_gerada(c):
    from gestao.viagens import ordens
    from gestao.viagens.models import OrdemServico

    ordem, _ = ordens.salvar(c.usuarios["operador"], motivo="Apoio no evento (teste)")
    grupo = _grupo(_secoes(c.usuarios["operador"])["documentos"], "ordens")
    assert f"ordem-{ordem.pk}" in _chaves(grupo)
    OrdemServico.objects.filter(pk=ordem.pk).update(documento_gerado_em=timezone.now())
    assert f"ordem-{ordem.pk}" not in _chaves(
        _grupo(_secoes(c.usuarios["operador"])["documentos"], "ordens"))


def test_envio_manual_leva_a_conferencia_e_respeita_a_unidade(c, settings):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    ps = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=c.ids["oficio_emitido"]).order_by("pk").first()
    _liberar(c, ps, timezone.localdate() + timedelta(days=10))
    grupo = _grupo(_secoes(c.usuarios["operador"])["envios"], "envios")
    assert grupo.total == 1
    item = grupo.itens[0]
    assert item.url == f"/viagens/envios/{ps.pk}/" and item.acao == "Conferir e enviar"
    assert any("Aviso de saque" in texto for _, texto in item.fatos)
    assert item.selo == "Sem telefone cadastrado"  # o servidor do cenário não tem celular
    acoes = [a.rotulo for a in _secoes(c.usuarios["operador"])["envios"].acoes]
    assert acoes == ["Atualizar pendências", "Enviados"]
    # A operadora da DPC não vê o servidor da ASCOM.
    assert not _secoes(c.usuarios["outra"])["envios"].grupos
    pagina = _cliente(c.usuarios["operador"]).get(URL + "?secao=envios")
    assert pagina.status_code == 200
    assert f'href="/viagens/envios/{ps.pk}/"'.encode() in pagina.content


def test_atualizar_volta_para_as_pendencias(c, settings):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    cliente = _cliente(c.usuarios["operador"])
    url = reverse("viagens:atualizar_envios")
    resposta = cliente.post(url, {"proximo": URL + "?secao=envios"})
    assert resposta.status_code == 302 and resposta["Location"] == URL + "?secao=envios"
    resposta = cliente.post(url, {"proximo": "https://outro.example/"})
    assert resposta["Location"] == reverse("viagens:envios_manuais")


def test_rotina_diaria_sincroniza_envios(c, settings):
    settings.AUTOMACAO_TRANSPORTE = "manual"
    ps = PrestacaoServidor.objects.filter(prestacao__oficio_id=c.ids["oficio_emitido"]).first()
    PrestacaoServidor.objects.filter(pk=ps.pk).update(
        data_liberacao_diarias=timezone.localdate())
    resultado = rotinas.rodar()
    assert resultado["pendências de envio manual"] != "falhou"
    assert envios_manuais.pendencias(c.usuarios["operador"]).filter(contexto__ps=ps.pk).exists()


def test_prestacao_vencida_saque_vencendo_e_devolvida(c):
    hoje = timezone.localdate()
    a, b = PrestacaoServidor.objects.filter(
        prestacao__oficio_id=c.ids["oficio_emitido"]).order_by("pk")
    PrestacaoServidor.objects.filter(pk=a.pk).update(prazo_limite_saque=hoje - timedelta(days=40))
    PrestacaoServidor.objects.filter(pk=b.pk).update(prazo_limite_saque=hoje + timedelta(days=2))
    secao = _secoes(c.usuarios["operador"])["prestacao"]
    vencida, saque = _grupo(secao, "prestacao_vencida"), _grupo(secao, "saque_vencendo")
    assert _chaves(vencida) == [f"prestacao-{a.pk}"]  # vencida não se repete em "saque"
    assert _chaves(saque) == [f"prestacao-{b.pk}"]
    assert vencida.itens[0].tom == "perigo" and saque.itens[0].selo == "Saque vence em 2 dias"
    assert saque.itens[0].url == reverse("viagens:prestacao_equipe", args=[b.prestacao_id])
    assert vencida.ver_todos.endswith("?aba=prestacao_vencida")
    PrestacaoServidor.objects.filter(pk=b.pk).update(
        situacao=PrestacaoServidor.Situacao.DEVOLVIDA, prazo_limite_saque=None)
    secao = _secoes(c.usuarios["operador"])["prestacao"]
    assert _chaves(_grupo(secao, "devolvidas")) == [f"prestacao-{b.pk}"]
    assert {a.rotulo for a in secao.acoes} <= {"Sem solicitação", "Sem comprovante"}
    assert not _secoes(c.usuarios["outra"])["prestacao"].grupos


def test_solicitacoes_de_evento_por_quem_age(c):
    from gestao.eventos import dominio
    from gestao.eventos.models import Solicitacao

    hoje = timezone.localdate()
    op = c.usuarios["operador"]
    rascunho = Solicitacao.objects.create(data_solicitacao=hoje, criado_por=op,
                                          data_inicio_evento=hoje + timedelta(days=5))
    aguardando = Solicitacao.objects.create(data_solicitacao=hoje, criado_por=op,
                                            status=dominio.AGUARDANDO)
    meus = _secoes(op)["eventos"]
    assert _chaves(_grupo(meus, "rascunhos")) == [f"evento-{rascunho.pk}"]
    assert _grupo(meus, "despacho") is None  # quem pede não despacha
    dg = Usuario.objects.create_user("dg", "dg@pc.pr.gov.br", None, nome="Diretoria")
    dg.groups.add(Group.objects.get(name="GESTOR_DG"))
    secao = _secoes(dg)["eventos"]
    assert _chaves(_grupo(secao, "despacho")) == [f"evento-{aguardando.pk}"]
    assert _grupo(secao, "rascunhos") is None  # o rascunho é de quem criou


def test_excecoes_da_automacao_pela_unidade(c):
    ascom = Unidade.objects.get(sigla="ASCOM")
    e = excecoes.abrir("contato", "teste-pendencias", "Contato sem opt-in (teste)",
                       unidade_id=ascom.pk, avisar=False)
    grupo = _grupo(_secoes(c.usuarios["operador"])["automacao"], "excecoes")
    assert _chaves(grupo) == [f"excecao-{e.pk}"]
    assert grupo.itens[0].url == reverse("automacao:excecao", args=[e.pk])
    assert not _secoes(c.usuarios["outra"])["automacao"].grupos


def test_em_dia_e_secao_vazia(c):
    nova = Unidade.objects.create(sigla="NOVA", nome="Unidade sem nada")
    u = Usuario.objects.create_user("nova", "nova@pc.pr.gov.br", None, nome="Operadora nova")
    u.groups.add(Group.objects.get(name="OPERADOR_VIAGENS"))
    Lotacao.objects.create(usuario=u, unidade=nova)
    cliente = _cliente(u)
    texto = cliente.get(URL).content.decode()
    assert "Em dia" in texto and "0 pendências" in texto
    assert "Nenhum documento esperando" in cliente.get(URL + "?secao=documentos").content.decode()
    # Seção pedida que não existe para a pessoa: volta para a visão geral.
    assert "Tudo o que está pendente" in cliente.get(URL + "?secao=coffee").content.decode()


def test_falha_de_uma_secao_nao_derruba_a_tela(c, monkeypatch):
    original = pendencias.secoes_de

    def com_falha(usuario):
        def quebra(usuario, hoje):
            raise RuntimeError("falha simulada")
        return [pendencias.Secao(s.slug, s.titulo, s.icone, s.descricao, s.pode, quebra,
                                 s.acoes, s.vazio, s.ordem) if s.slug == "documentos" else s
                for s in original(usuario)]

    monkeypatch.setattr(pendencias, "secoes_de", com_falha)
    resposta = _cliente(c.usuarios["operador"]).get(URL)
    assert resposta.status_code == 200
    texto = resposta.content.decode()
    assert "Não deu para carregar esta seção" in texto and "Prestação de contas" in texto


def test_consultas_nao_crescem_com_os_itens(c, django_assert_max_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from gestao.viagens import ordens

    cliente = _cliente(c.usuarios["gestor"])
    # Um de cada antes de medir: grupo vazio pula consultas (prefetch, leitura dos itens).
    ordens.salvar(c.usuarios["operador"], motivo="Apoio (teste)")
    primeira = PrestacaoServidor.objects.order_by("pk").first()
    PrestacaoServidor.objects.filter(pk=primeira.pk).update(
        prazo_limite_saque=timezone.localdate() - timedelta(days=40))
    cliente.get(URL)  # aquece sessão, permissões e cache de templates

    def contar() -> int:
        with CaptureQueriesContext(connection) as consultas:
            assert cliente.get(URL).status_code == 200
        return len(consultas)

    antes = contar()
    for _ in range(6):  # mais rascunhos, OS e todas as prestações vencidas
        services.criar_rascunho(c.usuarios["operador"], data_oficio=timezone.localdate())
        ordens.salvar(c.usuarios["operador"], motivo="Apoio (teste)")
    PrestacaoServidor.objects.update(
        prazo_limite_saque=timezone.localdate() - timedelta(days=40))
    assert contar() == antes
    with django_assert_max_num_queries(40):
        cliente.get(URL)
