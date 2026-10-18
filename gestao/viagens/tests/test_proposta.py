"""Proposta consolidada (AUT-14): a prévia não grava nem reserva número; "Criar rascunhos"
remonta com a mesma função, confere a assinatura e cria pelo lote existente; entrada mudada é
recusada; conflito aparece; fora do escopo é 404 e sem permissão é 403; a ferramenta tipada é
só leitura e não escolhe equipe."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio, Servidor, TipoViagem, Viatura
from gestao.viagens import proposta, services, viagem
from gestao.viagens.models import (
    Historico,
    LacunaNumeracao,
    LacunaOrdemServico,
    LacunaPlano,
    NumeracaoAnual,
    NumeracaoOrdemServico,
    NumeracaoPlano,
    Oficio,
    OrdemServico,
    PlanoTrabalho,
    Roteiro,
    TermoAutorizacao,
    Trecho,
    Viagem,
    Viajante,
)

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
MODELOS = (Viagem, Oficio, Viajante, Trecho, TermoAutorizacao, OrdemServico, PlanoTrabalho,
           Historico, Roteiro, NumeracaoAnual, LacunaNumeracao, NumeracaoOrdemServico,
           LacunaOrdemServico, NumeracaoPlano, LacunaPlano)


@pytest.fixture
def c():
    cen = cenario_completo()
    TipoViagem.objects.create(nome="Unidade Móvel")
    return cen


def _viagem(c) -> Viagem:
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.all()), motivo="Feira (teste)",
                        data_inicio=date(2030, 5, 10),
                        destinos=[Municipio.objects.get(nome="Ponta Grossa", uf="PR")],
                        vinculos={"roteiros": [Roteiro.objects.get(pk=c.ids["roteiro"])]})
    return Viagem.objects.get(pk=v.pk)


def _servidores():
    todos = list(Servidor.objects.filter(ativo=True).order_by("pk"))
    return todos[5], todos[9], todos[8]  # ASCOM, DPC (de fora), DPC (motorista da Master)


def _contagens() -> dict:
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM auditoria_evento")
        auditoria = cur.fetchone()[0]
    return {**{m.__name__: m.objects.count() for m in MODELOS}, "auditoria": auditoria}


def _entrada(v, servidores, motorista=None, viatura=None):
    return proposta.Entrada.de(v, servidores, motorista, viatura)


def test_previa_nao_grava_nem_numera(c):
    v = _viagem(c)
    a, b, m = _servidores()
    master = Viatura.objects.get(placa="ABC1D23")
    antes, proximo = _contagens(), services.resumo_numeracao()[0].proximo
    p = proposta.montar(c.usuarios["operador"], _entrada(v, [a, b], m, master))
    assert _contagens() == antes
    assert services.resumo_numeracao()[0].proximo == proximo
    assert Viagem.objects.get(pk=v.pk).atualizado_em == v.atualizado_em
    assert p.pode_criar and not p.bloqueios and len(p.assinatura) == 64
    tipos = {d.tipo: d for d in p.documentos}
    assert set(tipos) == {"roteiro", "oficio", "termo", "ordem", "plano"}
    assert not tipos["roteiro"].cria and tipos["oficio"].cria
    assert "nº atribuído ao criar" in tipos["oficio"].titulo
    assert b.nome in tipos["termo"].detalhe and a.nome not in tipos["termo"].detalhe
    assert [e.id for e in p.equipe] == [a.pk, b.pk, m.pk]  # o motorista entra na equipe
    assert next(e for e in p.equipe if e.id == m.pk).motorista
    # Diárias: o cálculo determinístico do domínio, com a tabela real, para os 3 servidores.
    roteiro = Roteiro.objects.get(pk=c.ids["roteiro"])
    esperado = services.calcular_informados(services.trechos_informados_do_roteiro(roteiro),
                                            roteiro.sede, servidores=3)
    assert Decimal(p.diarias.total) == esperado.total > 0
    assert p.diarias.rotulo.startswith("Estimativa para conferência")
    assert any("protocolo" in d.mensagem for d in p.depois)
    assert p.conflitos == []


def test_aplicar_cria_rascunhos_iguais_a_previa(c):
    v = _viagem(c)
    a, b, m = _servidores()
    master = Viatura.objects.get(placa="ABC1D23")
    op = c.usuarios["operador"]
    entrada = _entrada(v, [a, b], m, master)
    previa = proposta.montar(op, entrada)
    proximo = services.resumo_numeracao()[0].proximo
    _, r = proposta.aplicar(op, entrada, previa.assinatura)
    assert len(r.oficios) == 1 and r.ordem is not None and r.plano is not None and r.termos == 1
    oficio = Oficio.objects.get(pk=r.oficios[0].pk)
    assert oficio.situacao == Oficio.Situacao.RASCUNHO and not oficio.protocolo
    assert oficio.viagem_id == v.pk and oficio.viatura_id == master.pk
    # O número oficial só existe depois de "Criar rascunhos" — e é o que a prévia não tocou.
    assert oficio.numero == proximo
    assert list(oficio.viajantes.order_by("ordem").values_list("servidor_id", flat=True)) == [
        a.pk, b.pk, m.pk]
    assert oficio.viajantes.get(motorista=True).servidor_id == m.pk
    # Equivalência prévia × gravado (diárias calculadas pelo serviço ao salvar).
    assert oficio.diarias_total == Decimal(previa.diarias.total)
    termo = TermoAutorizacao.objects.get(viagem=v)  # os de outra unidade (DPC): b e o motorista
    assert set(termo.servidores.values_list("pk", flat=True)) == {b.pk, m.pk}


def test_entrada_mudada_depois_da_previa_e_recusada(c):
    v = _viagem(c)
    a, b, _ = _servidores()
    op = c.usuarios["operador"]
    previa = proposta.montar(op, _entrada(v, [a]))
    antes = _contagens()
    with pytest.raises(proposta.PropostaDesatualizada):
        proposta.aplicar(op, _entrada(v, [a, b]), previa.assinatura)
    assert _contagens() == antes
    # A viagem mudou depois da prévia (outra pessoa salvou): também recusa.
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.all()), motivo="Outro motivo",
                        data_inicio=date(2030, 5, 10),
                        destinos=[Municipio.objects.get(nome="Ponta Grossa", uf="PR")])
    antes = _contagens()
    with pytest.raises(proposta.PropostaDesatualizada):
        proposta.aplicar(op, _entrada(v, [a]), previa.assinatura)
    assert _contagens() == antes
    with pytest.raises(proposta.PropostaDesatualizada):
        proposta.aplicar(op, _entrada(v, [a]), "")


def test_conflito_de_agenda_aparece(c):
    v = _viagem(c)
    a, _, _ = _servidores()
    op = c.usuarios["operador"]
    roteiro = Roteiro.objects.get(pk=c.ids["roteiro"])
    t = services.trechos_informados_do_roteiro(roteiro)
    outro = services.criar_rascunho(op)
    services.adicionar_viajante(outro, op, a)
    services.salvar_trechos(outro, op, [
        services.TrechoInformado(t[0].origem_id, t[0].destino_id, t[0].saida_em,
                                 t[0].saida_em + timedelta(hours=2)),
        services.TrechoInformado(t[0].destino_id, t[0].origem_id,
                                 t[0].saida_em + timedelta(hours=5),
                                 t[0].saida_em + timedelta(hours=7))])
    p = proposta.montar(op, _entrada(v, [a]))
    assert len(p.conflitos) == 1 and a.nome in p.conflitos[0]
    assert outro.numero_formatado in p.conflitos[0]
    assert p.pode_criar  # conflito é aviso, não bloqueio
    cli = Client()
    cli.force_login(op)
    html = cli.get(reverse("viagens:proposta"), {
        "acao": "previa", "viagem": v.pk, "servidores": [a.pk], "termos": "on"}).content.decode()
    assert 'id="conflitos"' in html and outro.numero_formatado in html


def test_servidor_ja_no_oficio_da_viagem_bloqueia(c):
    v = _viagem(c)
    a, _, _ = _servidores()
    op = c.usuarios["operador"]
    entrada = _entrada(v, [a])
    proposta.aplicar(op, entrada, proposta.montar(op, entrada).assinatura)
    p = proposta.montar(op, entrada)
    assert not p.pode_criar and any("já está no" in b.mensagem for b in p.bloqueios)
    with pytest.raises(proposta.PropostaBloqueada):
        proposta.aplicar(op, entrada, p.assinatura)


def test_outra_unidade_e_404(c):
    v = _viagem(c)
    a, _, _ = _servidores()
    outra = c.usuarios["outra"]
    with pytest.raises(proposta.ForaDoEscopo):
        proposta.montar(outra, _entrada(v, [a]))
    cli = Client()
    cli.force_login(outra)
    assert cli.get(reverse("viagens:proposta"), {"viagem": v.pk}).status_code == 404
    assert cli.get(reverse("viagens:proposta"), {
        "acao": "previa", "viagem": v.pk, "servidores": [a.pk]}).status_code == 404
    antes = _contagens()
    r = cli.post(reverse("viagens:criar_proposta"), {
        "viagem": v.pk, "servidores": [a.pk], "assinatura": "x"})
    assert r.status_code == 404 and _contagens() == antes


def test_sem_permissao_e_403(c):
    v = _viagem(c)
    a, _, _ = _servidores()
    consulta = c.usuarios["consulta"]  # vê todas as viagens, mas não cria ofícios
    with pytest.raises(PermissionDenied):
        proposta.montar(consulta, _entrada(v, [a]))
    cli = Client()
    cli.force_login(consulta)
    assert cli.get(reverse("viagens:proposta")).status_code == 403
    antes = _contagens()
    r = cli.post(reverse("viagens:criar_proposta"), {
        "viagem": v.pk, "servidores": [a.pk], "assinatura": "x"})
    assert r.status_code == 403 and _contagens() == antes


def test_tela_previa_e_criar(c):
    v = _viagem(c)
    a, b, _ = _servidores()
    cli = Client()
    cli.force_login(c.usuarios["operador"])
    url = reverse("viagens:proposta")
    html = cli.get(url, {"viagem": v.pk}).content.decode()
    assert "Ver prévia" in html and 'name="assinatura"' not in html
    antes = _contagens()
    r = cli.get(url, {"acao": "previa", "viagem": v.pk, "servidores": [a.pk, b.pk],
                      "termos": "on", "ordem": "on", "plano": "on"})
    html = r.content.decode()
    assert r.status_code == 200 and _contagens() == antes
    assert "Prévia: nada foi gravado e nenhum número foi reservado." in html
    assert "Estimativa para conferência" in html and 'name="assinatura"' in html
    assinatura = r.context["previa"].assinatura
    dados = {"viagem": v.pk, "servidores": [a.pk, b.pk], "termos": "1", "ordem": "1",
             "plano": "1", "assinatura": assinatura}
    # Entrada adulterada depois da prévia: 409, nada criado, a prévia nova aparece.
    r = cli.post(reverse("viagens:criar_proposta"), {**dados, "servidores": [a.pk]})
    assert r.status_code == 409 and _contagens() == antes
    assert "Nada foi criado" in r.content.decode()
    r = cli.post(reverse("viagens:criar_proposta"), dados)
    assert r.status_code == 302 and r["Location"].endswith("#documentos")
    assert Oficio.objects.filter(viagem=v).count() == 1
    # Sem ninguém: erro no formulário, nada calculado.
    r = cli.get(url, {"acao": "previa", "viagem": v.pk})
    assert r.status_code == 422 and r.context["previa"] is None


def test_tela_vazia_sem_viagens(c):
    cli = Client()
    cli.force_login(c.usuarios["operador"])
    Viagem.objects.update(situacao=Viagem.Situacao.CANCELADA)
    html = cli.get(reverse("viagens:proposta")).content.decode()
    assert "Nenhuma viagem para preparar" in html


def test_ferramenta_previa_e_leitura_e_nao_cria(c):
    from gestao.automacao import ferramentas

    proposta.registrar_ferramentas()
    f = ferramentas.obter("viagens.proposta_previa")
    assert f is not None and f.risco == ferramentas.LEITURA
    assert [x.nome for x in ferramentas.todas() if x.nome.startswith("viagens.proposta")] == [
        "viagens.proposta_previa"]  # não há ferramenta que crie rascunhos
    v = _viagem(c)
    a, b, _ = _servidores()
    op = c.usuarios["operador"]
    antes = _contagens()
    r = ferramentas.executar("viagens.proposta_previa",
                             {"viagem": v.pk, "servidores": [a.pk, b.pk]}, usuario=op)
    saida = r.saida
    assert saida["aviso"].startswith("Prévia: nada foi gravado")
    assert saida["assinatura"] == proposta.montar(op, _entrada(v, [a, b])).assinatura
    assert {d["tipo"] for d in saida["documentos"]} >= {"oficio", "termo"}
    assert [e["id"] for e in saida["equipe"]] == [a.pk, b.pk]
    depois = _contagens()
    assert {k: v for k, v in depois.items() if k != "auditoria"} == {
        k: v for k, v in antes.items() if k != "auditoria"}  # só o registro da execução
    with pytest.raises(PermissionDenied):
        ferramentas.executar("viagens.proposta_previa",
                             {"viagem": v.pk, "servidores": [a.pk]}, usuario=c.usuarios["outra"])
    with pytest.raises(ferramentas.FerramentaInvalida):
        ferramentas.executar("viagens.proposta_previa",
                             {"viagem": v.pk, "servidores": ["Fulano"]}, usuario=op)


def test_sem_roteiro_avisa_e_nao_estima(c):
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    viagem.salvar_dados(op, v.pk, tipos=[], motivo="Sem roteiro",
                        data_inicio=timezone.localdate() + timedelta(days=40),
                        destinos=[Municipio.objects.get(nome="Londrina", uf="PR")])
    a, _, _ = _servidores()
    p = proposta.montar(op, _entrada(v, [a]))
    assert p.roteiro is None and p.diarias.erro and p.diarias.total == ""
    assert any("sem trechos" in x.mensagem for x in p.avisos)
    assert isinstance(p.calculada_em, datetime)


def test_depois_da_previa_o_passo_1_vira_resumo(c):
    """Revisão de UX (P1): com a prévia na tela, as escolhas não ficam editáveis ao lado do
    "Criar" (que usaria a prévia, não o que foi mexido); "Alterar escolhas" volta ao formulário
    preenchido, sem prévia."""
    v = _viagem(c)
    a, b, _ = _servidores()
    cli = Client()
    cli.force_login(c.usuarios["operador"])
    url = reverse("viagens:proposta")
    r = cli.get(url, {"acao": "previa", "viagem": v.pk, "servidores": [a.pk, b.pk],
                      "termos": "on"})
    html = r.content.decode()
    assert 'id="form-proposta"' not in html and "Alterar escolhas" in html
    alterar = r.context["url_alterar"]
    assert "acao=alterar" in alterar and f"servidores={a.pk}" in alterar
    r = cli.get(alterar)
    html = r.content.decode()
    assert r.status_code == 200 and r.context["previa"] is None
    assert 'id="form-proposta"' in html and 'name="assinatura"' not in html
    assert r.context["form"]["viagem"].value() == str(v.pk)
