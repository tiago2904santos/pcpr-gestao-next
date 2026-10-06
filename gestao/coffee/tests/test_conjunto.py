"""CB3b: pagamento conjunto — candidatas (mesmo lote, sem protocolo, fora de outro grupo),
um só número de ofício, campos espelhados com histórico, protocolo e atesto só com a nota
de todas, e a principal que sai passa o papel à próxima."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import conjunto, financeiro, pedidos
from gestao.coffee.models import Contrato, Fornecedor, Lote, Movimento, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def tres():
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="1/2026", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=300))
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500)
    lote.municipios.set([curitiba])
    outro = Lote.objects.create(contrato=c, numero=2, exercicio=str(hoje.year),
                                quantidade_total=500)
    os_ = [pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                              "descricao": f"Evento {i}", "quantidade": 10}).solicitacao
           for i in range(3)]
    fora = pedidos.salvar(u, {"municipio": curitiba, "data_solicitacao": hoje, "numero": "",
                              "descricao": "Outro lote", "quantidade": 10}).solicitacao
    Solicitacao.objects.filter(pk=fora.pk).update(lote=outro)
    return u, os_, fora


def _fin(s, **dados):
    s.refresh_from_db()
    return {**{c: getattr(s, c) for c in financeiro.CAMPOS}, **dados}


def test_candidatas_e_um_so_oficio_espelhado(tres):
    u, (a, b, c), fora = tres
    assert {x.pk for x in conjunto.candidatas(a)} == {b.pk, c.pk}  # outro lote fica de fora
    with pytest.raises(pedidos.PedidoInvalido, match="Só entram OS do mesmo lote"):
        conjunto.definir(u, a.pk, [fora.pk])
    grupo = conjunto.definir(u, a.pk, [b.pk, c.pk])
    assert [x.pk for x in grupo] == [a.pk, b.pk, c.pk]
    for x in (b, c):
        financeiro.salvar_financeiro(u, x.pk, _fin(x, nota_fiscal=f"9{x.pk}"))
    a = financeiro.salvar_financeiro(u, a.pk, _fin(a, nota_fiscal="1", numero_oficio="77"))
    b.refresh_from_db()
    assert a.numero_oficio == b.numero_oficio == f"77/{timezone.localdate().year}"
    assert Movimento.objects.filter(solicitacao=b, texto__startswith=f"Copiado da {a}").exists()
    assert conjunto.candidatas(fora).count() == 0


def test_protocolo_so_com_a_nota_de_todas_e_espelhado(tres):
    u, (a, b, _c), _f = tres
    conjunto.definir(u, a.pk, [b.pk])
    financeiro.salvar_financeiro(u, a.pk, _fin(a, nota_fiscal="1"))
    with pytest.raises(pedidos.PedidoInvalido, match="falta a nota da"):
        financeiro.registrar_marco(u, a.pk, "123456789")
    financeiro.salvar_financeiro(u, b.pk, _fin(b, nota_fiscal="2"))
    financeiro.registrar_marco(u, a.pk, "123456789")
    financeiro.registrar_marco(u, a.pk, "02/03/2026")
    b.refresh_from_db()
    assert b.protocolo_pagamento == "12.345.678-9" and b.atesto_em == date(2026, 3, 2)
    assert b.situacao == "aguardando_ob"
    with pytest.raises(pedidos.PedidoInvalido, match="Só entram"):
        conjunto.definir(u, a.pk, [])  # com protocolo, o grupo não muda


def test_principal_cancelada_passa_o_papel(tres):
    u, (a, b, c), _f = tres
    conjunto.definir(u, a.pk, [b.pk, c.pk])
    pedidos.cancelar(u, a.pk, "Evento adiado")
    b.refresh_from_db()
    c.refresh_from_db()
    assert b.pagamento_com_id is None and c.pagamento_com_id == b.pk
    assert Movimento.objects.filter(solicitacao=c,
                                    texto__contains="foi cancelada e saiu").exists()
    pedidos.excluir(u, c.pk)
    assert not conjunto.em_grupo(Solicitacao.objects.get(pk=b.pk))


def test_tela_do_pagamento_conjunto(tres):
    u, (a, b, _c), _f = tres
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:solicitacao", args=[a.pk])).content.decode()
    assert "Salvar pagamento conjunto" in html and str(b) in html
    r = cli.post(reverse("coffee:conjunto", args=[a.pk]), {"juntas": [str(b.pk)]})
    assert r.status_code == 302
    html = cli.get(reverse("coffee:solicitacao", args=[b.pk])).content.decode()
    assert "Pagamento conjunto (2 OS" in html and "(principal)" in html
