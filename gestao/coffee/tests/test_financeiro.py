"""CB3a: o fluxo financeiro da solicitação de coffee break — etapas 2 e 3 com a ordem dos
marcos, quantidade faturada e o saldo, ofício com número, protocolo no formato, andamento
do próximo marco, concluída bloqueada, reabrir/encerrar correção com o histórico campo a
campo, e as telas."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import financeiro, pedidos, queries
from gestao.coffee.models import Contrato, Fornecedor, Lote, Movimento, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _usuario(login, *papeis):
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


@pytest.fixture
def os_():
    u = _usuario("ana", "ASCOM_COFFEE_BREAK")
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="1/2026", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=100)
    lote.municipios.set([curitiba])
    s = pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Evento", "quantidade": 60,
                           "data_evento": hoje - timedelta(days=1)},
                       retroativo=True, justificativa="Já aconteceu").solicitacao
    return u, s


def _fin(s, **dados):
    base = {c: getattr(s, c) for c in financeiro.CAMPOS}
    return {**base, **dados}


def test_ordem_dos_marcos_e_mensagens(os_):
    u, s = os_
    with pytest.raises(pedidos.PedidoInvalido, match="Informe a nota fiscal antes do protocolo"):
        financeiro.salvar_financeiro(u, s.pk, _fin(s, protocolo_pagamento="123456789"))
    with pytest.raises(pedidos.PedidoInvalido, match=r"00.000.000-0"):
        financeiro.salvar_financeiro(u, s.pk, _fin(s, nota_fiscal="1", protocolo_pagamento="12"))
    s = financeiro.salvar_financeiro(u, s.pk, _fin(s, nota_fiscal="8957",
                                                    protocolo_pagamento="123456789"))
    assert s.protocolo_pagamento == "12.345.678-9" and s.protocolo_pcpr == "12.345.678-9"
    assert s.numero_oficio == f"1/{timezone.localdate().year}" and s.data_oficio
    assert s.situacao == "aguardando_atesto"
    with pytest.raises(pedidos.PedidoInvalido, match="a nota não pode ficar em branco"):
        financeiro.salvar_financeiro(u, s.pk, _fin(s, nota_fiscal=""))
    with pytest.raises(pedidos.PedidoInvalido, match="não pode ser anterior ao atesto"):
        financeiro.salvar_financeiro(u, s.pk, _fin(s, atesto_em=date(2026, 3, 10),
                                                    ordem_bancaria_em=date(2026, 3, 1)))


def test_quantidade_faturada_mexe_no_saldo_e_no_historico(os_):
    u, s = os_
    s = financeiro.salvar_financeiro(u, s.pk, _fin(s, nota_fiscal="1", quantidade_faturada=50))
    assert queries.saldo(s.lote).restante == 50
    assert Movimento.objects.filter(solicitacao=s,
                                    texto__contains="10 voltaram ao saldo do lote").exists()
    with pytest.raises(pedidos.PedidoInvalido, match="restam 50 de 100"):
        pedidos.salvar(u, {"municipio": s.municipio, "data_solicitacao": s.data_solicitacao,
                           "numero": "", "descricao": "Outro", "quantidade": 51})
    with pytest.raises(pedidos.PedidoInvalido, match="restam 100 de 100"):
        financeiro.salvar_financeiro(u, s.pk, _fin(s, quantidade_faturada=101))


def test_andamento_do_proximo_marco_ate_concluir(os_):
    u, s = os_
    with pytest.raises(pedidos.PedidoInvalido, match="Informe: número da nota fiscal"):
        financeiro.registrar_marco(u, s.pk, "")
    financeiro.registrar_marco(u, s.pk, "8957", "Nota recebida por e-mail")
    financeiro.registrar_marco(u, s.pk, "123456789")
    financeiro.registrar_marco(u, s.pk, "02/03/2026")
    with pytest.raises(pedidos.PedidoInvalido, match="Data inválida"):
        financeiro.registrar_marco(u, s.pk, "31/02/2026")
    with pytest.raises(pedidos.PedidoInvalido, match="não pode ser anterior ao atesto"):
        financeiro.registrar_marco(u, s.pk, "01/03/2026")
    financeiro.registrar_marco(u, s.pk, "05/03/2026")
    s = financeiro.registrar_marco(u, s.pk, "06/03/2026")
    assert s.situacao == "concluida" and s.bloqueada
    assert Movimento.objects.filter(
        solicitacao=s, texto="Número da nota fiscal: 8957 — Nota recebida por e-mail").exists()
    with pytest.raises(pedidos.PedidoInvalido, match="não tem marco a registrar"):
        s.em_correcao = True  # (mesmo sem bloqueio, não há marco depois do envio)
        s.save()
        financeiro.registrar_marco(u, s.pk, "x")


def test_reabrir_e_encerrar_correcao_so_o_administrador(os_):
    u, s = os_
    Solicitacao.objects.filter(pk=s.pk).update(
        nota_fiscal="1", protocolo_pagamento="12.345.678-9", atesto_em=date(2026, 3, 1),
        ordem_bancaria_em=date(2026, 3, 2), envio_empresa_em=date(2026, 3, 3))
    from django.core.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        financeiro.reabrir_correcao(u, s.pk, "erro de digitação")
    adm = _usuario("adm", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR")
    with pytest.raises(pedidos.PedidoInvalido, match="Informe o motivo da correção"):
        financeiro.reabrir_correcao(adm, s.pk, " ")
    financeiro.reabrir_correcao(adm, s.pk, "Nota com número errado")
    s.refresh_from_db()
    assert not s.bloqueada
    s = financeiro.salvar_financeiro(adm, s.pk, _fin(s, nota_fiscal="2"))
    assert Movimento.objects.filter(solicitacao=s,
                                    texto="Correção — nº da nota fiscal: 1 → 2.").exists()
    financeiro.encerrar_correcao(adm, s.pk)
    s.refresh_from_db()
    assert s.bloqueada
    with pytest.raises(pedidos.PedidoInvalido, match="não está aberta para correção"):
        financeiro.encerrar_correcao(adm, s.pk)


def test_telas_do_fluxo(os_):
    u, s = os_
    c = Client()
    c.force_login(u)
    html = c.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Nota fiscal e ofício" in html and "Registrar andamento" in html
    assert 'aria-current="step"' in html
    from gestao.coffee.forms_pedido import versao_de
    r = c.post(reverse("coffee:financeiro", args=[s.pk]), {
        "versao": versao_de(s), "nota_fiscal": "", "protocolo_pagamento": "123456789"})
    assert r.status_code == 422 and "Informe a nota fiscal antes" in r.content.decode()
    r = c.post(reverse("coffee:financeiro", args=[s.pk]), {
        "versao": versao_de(s), "nota_fiscal": "8957", "quantidade_faturada": "55"})
    assert r.status_code == 302
    s.refresh_from_db()
    assert s.quantidade_faturada == 55 and s.numero_oficio
    r = c.post(reverse("coffee:andamento", args=[s.pk]), {"valor": "123456789"}, follow=True)
    assert "Andamento registrado: Aguardando atesto." in r.content.decode()
    r = c.post(reverse("coffee:financeiro", args=[s.pk]), {"versao": "2020", "nota_fiscal": "1"})
    assert "alterada por outra pessoa" in r.content.decode()
