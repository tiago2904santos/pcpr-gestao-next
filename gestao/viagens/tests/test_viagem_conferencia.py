"""Conferência da viagem (módulo 8b): quadro de prontidão por etapa (com links) e coerência
entre a viagem e os documentos, com "Aplicar em todos" que poupa o que tem via assinada
(paridade com prontidao.py e coerencia.py da referência)."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio, TipoViagem
from gestao.viagens import assinados, termos, viagem, viagem_conferencia
from gestao.viagens.models import Oficio, OrdemServico, TermoAutorizacao, Viagem

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.7\n%%EOF\n"


@pytest.fixture
def c():
    cen = cenario_completo()
    TipoViagem.objects.create(nome="Unidade Móvel")
    return cen


def _m(nome):
    return Municipio.objects.get(nome=nome, uf="PR")


def _viagem_pronta_para_conferir(c) -> Viagem:
    op = c.usuarios["operador"]
    v = viagem.criar(op)
    viagem.salvar_dados(op, v.pk, tipos=list(TipoViagem.objects.all()),
                        data_inicio=date(2030, 5, 10), data_fim=date(2030, 5, 12),
                        destinos=[_m("Londrina")])
    return Viagem.objects.get(pk=v.pk)


def test_quadro_da_viagem_vazia_lista_as_etapas_na_ordem(c):
    v = viagem.criar(c.usuarios["operador"])
    q = viagem_conferencia.quadro(v)
    assert [e.chave for e in q.etapas] == ["dados", "roteiro", "oficios", "equipe", "ordem",
                                           "plano", "termos", "assinaturas", "protocolo"]
    dados = q.etapas[0]
    assert [i.mensagem for i in dados.itens] == ["Informe o tipo da viagem.",
                                                 "Informe o período da viagem.",
                                                 "Informe o destino da viagem."]
    assert dados.itens[0].link.endswith("#dados") and not q.pronta
    assert "Crie a ordem de serviço." in [i.mensagem for e in q.etapas for i in e.itens]


def test_quadro_com_oficio_emitido_pede_assinatura_e_termos(c):
    v = _viagem_pronta_para_conferir(c)
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    viagem.salvar_dados(c.usuarios["operador"], v.pk, tipos=list(v.tipos.all()),
                        data_inicio=v.data_inicio, data_fim=v.data_fim,
                        destinos=[d.municipio for d in v.destinos.all()],
                        vinculos={"oficios": [oficio]})
    mensagens = [i.mensagem for e in viagem_conferencia.quadro(v).etapas for i in e.itens]
    assert f"{oficio}: falta anexar a versão assinada." in mensagens
    assert not any(m.startswith("Informe o") for m in mensagens)


def test_coerencia_da_os_e_do_termo(c):
    op = c.usuarios["operador"]
    v = _viagem_pronta_para_conferir(c)
    ordem = viagem.novo_documento(op, v.pk, "ordem")
    OrdemServico.objects.filter(pk=ordem.pk).update(data_inicio=date(2030, 5, 11))
    termo = viagem.novo_documento(op, v.pk, "termo")
    termos.salvar(op, pk=termo.pk, evento="x", data_inicio=date(2030, 5, 10),
                  data_fim=date(2030, 5, 12), destinos=[_m("Maringá")],
                  versao=termos.versao_de(TermoAutorizacao.objects.get(pk=termo.pk)))
    chaves = {d.chave for d in viagem_conferencia.coerencia(v)}
    assert f"ordem-{ordem.pk}:periodo" in chaves and f"termo-{termo.pk}:destinos" in chaves
    d = next(x for x in viagem_conferencia.coerencia(v) if x.chave == f"ordem-{ordem.pk}:periodo")
    assert d.atual == "11/05/2030 a 12/05/2030" and d.esperado == "10/05/2030 a 12/05/2030"


def test_aplicar_em_todos_poupa_o_assinado(c):
    op = c.usuarios["operador"]
    v = _viagem_pronta_para_conferir(c)
    ordem = viagem.novo_documento(op, v.pk, "ordem")
    OrdemServico.objects.filter(pk=ordem.pk).update(data_inicio=date(2030, 5, 11))
    termo = viagem.novo_documento(op, v.pk, "termo")
    termos.salvar(op, pk=termo.pk, evento="x", data_inicio=date(2030, 5, 10),
                  data_fim=date(2030, 5, 12), destinos=[_m("Maringá")],
                  versao=termos.versao_de(TermoAutorizacao.objects.get(pk=termo.pk)))
    assinados.anexar(op, assinados.Alvo("termo", TermoAutorizacao.objects.get(pk=termo.pk),
                                        termos.GENERICO), nome="t.pdf", conteudo=PDF)
    r = viagem_conferencia.aplicar(op, v.pk)
    assert str(OrdemServico.objects.get(pk=ordem.pk)) in r.atualizados
    assert r.pulados == [(str(TermoAutorizacao.objects.get(pk=termo.pk)), "destinos")]
    assert OrdemServico.objects.get(pk=ordem.pk).data_inicio == date(2030, 5, 10)
    destinos_termo = [d.municipio for d in TermoAutorizacao.objects.get(pk=termo.pk).destinos.all()]
    assert destinos_termo == [_m("Maringá")]  # assinado: não mexe


def test_tela_mostra_conferencia_e_aplica(c):
    op = c.usuarios["operador"]
    v = _viagem_pronta_para_conferir(c)
    ordem = viagem.novo_documento(op, v.pk, "ordem")
    OrdemServico.objects.filter(pk=ordem.pk).update(data_inicio=date(2030, 5, 11))
    cli = Client()
    cli.force_login(op)
    html = cli.get(reverse("viagens:editar_viagem", args=[v.pk])).content.decode()
    assert "Conferência" in html and "não bate" in html and "Aplicar em todos" in html
    r = cli.post(reverse("viagens:aplicar_coerencia_viagem", args=[v.pk]), follow=True)
    assert "Documentos atualizados com os dados da viagem" in r.content.decode()
    r = cli.post(reverse("viagens:aplicar_coerencia_viagem", args=[v.pk]), follow=True)
    assert "Nada a corrigir" in r.content.decode()


def test_consulta_nao_aplica(c):
    v = _viagem_pronta_para_conferir(c)
    cli = Client()
    cli.force_login(c.usuarios["consulta"])
    r = cli.post(reverse("viagens:aplicar_coerencia_viagem", args=[v.pk]), follow=True)
    assert "Reative a viagem antes de corrigir" in r.content.decode()
