"""Relatório técnico (módulo 9c): nasce com o custeio padrão, a diária liberada, as trocas
do diário e os textos prontos padrão (com marcadores); sugestões do ofício/viagem/plano só
como valor inicial; diária recebida nunca acima da liberada; trava pela equipe; pendência
na finalização; permissões; a folha e o documento por servidor."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import ModeloTexto
from gestao.viagens import diario, prestacao, relatorio
from gestao.viagens.models import PrestacaoContas, PrestacaoServidor, RelatorioTecnico

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db


@pytest.fixture
def c():
    return cenario_completo()


def _p(c) -> PrestacaoContas:
    return PrestacaoContas.objects.select_related("oficio").get(
        oficio_id=c.ids["oficio_emitido"])


def _cliente(c, login: str) -> Client:
    cliente = Client()
    cliente.force_login(c.usuarios[login])
    return cliente


def test_nasce_com_padroes_e_marcadores(c):
    p = _p(c)
    ModeloTexto.objects.create(tipo="rt_motivo", nome="Padrão", padrao=True,
                               texto="Evento em {destino} ({periodo}). {desconhecido}")
    d = diario.obter(p)
    diario.trocar_motorista_e_viatura(c.usuarios["operador"], d.pk, motorista_modo="outro_oficio",
                                      motorista_nome="Fulano de Tal", viatura_modo="oficio")
    rt = relatorio.obter(p)
    assert (rt.translado, rt.combustivel, rt.passagem) == ("Não houve", "Cartão Prime",
                                                           "Não houve")
    assert rt.diaria.startswith("R$ ")
    assert rt.motivo.startswith("Evento em Arapongas/PR (") and "{desconhecido}" in rt.motivo
    assert "Fulano de Tal" in rt.info_complementares
    # Abrir de novo não sobrescreve o que a equipe escreveu.
    relatorio.salvar(c.usuarios["operador"], rt.pk, {"motivo": "Escrito pela equipe."})
    assert relatorio.obter(p).motivo == "Escrito pela equipe."


def test_sugestoes_so_como_valor_inicial(c):
    p = _p(c)
    s = relatorio.sugestoes(p)
    assert s["motivo"] == p.oficio.motivo
    relatorio.obter(p)
    html = _cliente(c, "operador").get(reverse("viagens:relatorio", args=[p.pk])).content.decode()
    assert "Sugestão — ainda não gravada" in html
    assert RelatorioTecnico.objects.get(prestacao=p).motivo == ""


def test_custeio_outro_e_diaria_recebida(c):
    p = _p(c)
    rt = relatorio.obter(p)
    op = c.usuarios["operador"]
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    liberada = prestacao.diaria_liberada(a)
    erros = relatorio.salvar(op, rt.pk, {
        "translado": "__outro__", "translado_outro": "Táxi da rodoviária",
        "combustivel": "valor estranho", f"ps-{a.pk}-diaria": "R$ 87,00 (saque)"})
    assert erros == {}
    rt.refresh_from_db()
    a.refresh_from_db()
    assert rt.translado == "Táxi da rodoviária" and rt.combustivel == "Cartão Prime"
    assert (a.diaria_valor_override, a.diaria_valor_override_observacao) == (
        Decimal("87.00"), "(saque)")
    assert relatorio.diaria_do_servidor(rt, a) == "R$ 87,00 (saque)"
    acima = liberada + Decimal("1")
    erros = relatorio.salvar(op, rt.pk, {"conclusao": "Texto grava mesmo assim.",
                                         f"ps-{a.pk}-diaria": f"{acima}"})
    assert "não pode passar do liberado" in erros[f"ps-{a.pk}-diaria"]
    rt.refresh_from_db()
    assert rt.conclusao == "Texto grava mesmo assim."
    assert relatorio.salvar(op, rt.pk, {f"ps-{a.pk}-diaria": "abc"})[f"ps-{a.pk}-diaria"]
    relatorio.salvar(op, rt.pk, {f"ps-{a.pk}-diaria": ""})
    a.refresh_from_db()
    assert a.diaria_valor_override is None  # vazio volta para a liberada


def test_pendencia_e_trava(c):
    p = _p(c)
    op = c.usuarios["operador"]
    ps = prestacao.ativos().filter(prestacao=p).first()
    assert relatorio.PENDENCIA in prestacao.pendencias(ps)
    rt = relatorio.obter(p)
    relatorio.salvar(op, rt.pk, {"motivo": "a", "atividade": "b", "conclusao": "c"})
    assert relatorio.PENDENCIA not in prestacao.pendencias(ps)
    assert relatorio.preenchidos([p.pk]) == {p.pk}
    for linha in prestacao.ativos().filter(prestacao=p):
        prestacao.finalizar(op, linha.pk, "Teste da trava.")
    with pytest.raises(relatorio.RelatorioInvalido, match="reabra para editar"):
        relatorio.salvar(op, rt.pk, {"motivo": "x"})


def test_permissoes(c):
    p = _p(c)
    outra, consulta = _cliente(c, "outra"), _cliente(c, "consulta")
    assert outra.get(reverse("viagens:relatorio", args=[p.pk])).status_code == 404
    assert outra.post(reverse("viagens:autosave_relatorio", args=[p.pk])).status_code == 404
    r = consulta.get(reverse("viagens:relatorio", args=[p.pk]))
    assert r.status_code == 200 and 'name="motivo"' not in r.content.decode()
    assert not RelatorioTecnico.objects.filter(prestacao=p).exists()
    assert consulta.post(reverse("viagens:autosave_relatorio", args=[p.pk]),
                         {"motivo": "x"}).json()["salvo"] is False


def test_folha_autosave_e_documentos(c, django_assert_max_num_queries):
    p = _p(c)
    op = _cliente(c, "operador")
    with django_assert_max_num_queries(40):
        r = op.get(reverse("viagens:relatorio", args=[p.pk]))
    assert r.status_code == 200 and "Valores usados" in r.content.decode()
    r = op.post(reverse("viagens:autosave_relatorio", args=[p.pk]),
                {"motivo": "Feira em Arapongas.", "atividade": "Atendimento.",
                 "conclusao": "Tudo certo.", "passagem": "Não houve"})
    assert r.json()["salvo"] is True
    a = PrestacaoServidor.objects.filter(prestacao=p).order_by("servidor__nome").first()
    r = op.post(reverse("viagens:autosave_relatorio", args=[p.pk]),
                {f"ps-{a.pk}-diaria": "999999"})
    assert r.json()["salvo"] is False and "liberado" in r.json()["mensagem"]
    rt = RelatorioTecnico.objects.get(prestacao=p)
    assert relatorio.nome_do_arquivo(rt, a, "pdf").startswith("RT_")
    r = op.get(reverse("viagens:documento_relatorio", args=[p.pk, a.pk, "pdf"]))
    assert r["Content-Type"] == "application/pdf" and r.content[:4] == b"%PDF"
    r = op.get(reverse("viagens:documento_relatorio", args=[p.pk, a.pk, "docx"]))
    assert r.content[:2] == b"PK" and ".docx" in r["Content-Disposition"]
    outro = PrestacaoServidor.objects.exclude(prestacao=p).first()
    if outro is not None:
        assert op.get(reverse("viagens:documento_relatorio",
                              args=[p.pk, outro.pk, "pdf"])).status_code == 404
    # A lista da prestação leva ao relatório.
    assert reverse("viagens:relatorio", args=[p.pk]) in op.get(
        reverse("viagens:prestacoes")).content.decode()


def test_textos_prontos_por_campo_com_marcadores(c):
    p = _p(c)
    ModeloTexto.objects.create(tipo="rt_conclusao", nome="Concluído", texto="Feito em {destino}.")
    prontos = relatorio.textos_prontos(p)
    assert prontos["conclusao"][0][2] == "Feito em Arapongas/PR."
    assert prontos["motivo"] == []


def test_sugerir_texto_pela_tela(c):
    p = _p(c)
    relatorio.obter(p)
    op = _cliente(c, "operador")
    r = op.post(reverse("viagens:sugerir_relatorio", args=[p.pk, "conclusao"]),
                {"atividade": "Apoiar a ação"})
    texto = r.json()["texto"]
    assert "foi realizada conforme o planejado" in texto and "Apoiar a ação" in texto
    assert "Arapongas/PR" in texto
    r = op.post(reverse("viagens:sugerir_relatorio", args=[p.pk, "medidas"]))
    assert r.json()["texto"].startswith("Recomenda-se ao órgão:")
    assert op.post(reverse("viagens:sugerir_relatorio", args=[p.pk, "motivo"])).status_code == 404
    consulta = _cliente(c, "consulta")
    assert consulta.post(reverse("viagens:sugerir_relatorio",
                                 args=[p.pk, "conclusao"])).status_code == 403
    assert RelatorioTecnico.objects.get(prestacao=p).conclusao == ""  # nunca grava


def test_copiar_de_outro_rt_do_mesmo_destino(c):
    from gestao.viagens.models import Oficio, Trecho

    p = _p(c)
    # Outro ofício da unidade com o mesmo destino e um RT escrito.
    outro = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    Trecho.objects.filter(oficio=outro, ordem=1).update(
        destino=Trecho.objects.get(oficio=p.oficio, ordem=1).destino)
    p2 = PrestacaoContas.objects.create(oficio=outro)
    RelatorioTecnico.objects.create(prestacao=p2, conclusao="Conclusão do outro ofício.")
    RelatorioTecnico.objects.create(prestacao=PrestacaoContas.objects.create(
        oficio=Oficio.objects.get(pk=c.ids["oficio_vazio"])), conclusao="Sem destino comum.")
    lista = relatorio.para_copiar(p)
    assert [item["rotulo"] for item in lista] == [
        f"Ofício {outro.numero_formatado} · mesmo destino"]
    assert lista[0]["textos"]["conclusao"] == "Conclusão do outro ofício."
    html = _cliente(c, "operador").get(reverse("viagens:relatorio", args=[p.pk])).content.decode()
    assert "Copiar de outro relatório técnico" in html and 'id="rts-para-copiar"' in html
