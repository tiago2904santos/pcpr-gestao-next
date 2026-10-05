"""Conflitos de agenda entre módulos (plataforma.conflitos): o servidor de um ofício que é
palestrante no mesmo dia aparece nos dois lados; viatura e motorista no ofício; pedido
repetido de palestra; cancelados e o próprio registro não contam; encostar não é sobrepor."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from gestao.palestras import conflitos as conflitos_palestras
from gestao.palestras import services as palestras
from gestao.palestras.models import Palestrante
from gestao.plataforma import conflitos
from gestao.viagens import conflitos as conflitos_viagens
from gestao.viagens import services
from gestao.viagens.models import Oficio
from gestao.viagens.tests.cenarios import cenario_completo

pytestmark = pytest.mark.django_db


def test_regras_do_periodo():
    um = timezone.make_aware(datetime(2026, 10, 5, 8))
    dois = timezone.make_aware(datetime(2026, 10, 5, 12))
    tres = timezone.make_aware(datetime(2026, 10, 5, 17))
    assert conflitos.sobrepoe(um, tres, dois, tres)
    assert not conflitos.sobrepoe(um, dois, dois, tres)  # encostar não conta
    inicio, fim = conflitos.periodo_de_datas(datetime(2026, 10, 5).date())
    assert (fim - inicio) == timedelta(days=1)
    assert conflitos.formatar_periodo(inicio, fim, dia_inteiro=True) == "em 05/10/2026"
    assert conflitos.consulta(None, fim) is None
    assert conflitos.conflitos(conflitos.consulta(inicio, fim)) == []  # sem recurso


def test_oficio_x_palestra_nos_dois_sentidos():
    c = cenario_completo()
    oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    servidor = oficio.viajantes.first().servidor
    dia = timezone.localtime(oficio.trechos.order_by("ordem").first().saida_em).date()
    ascom = c.usuarios["operador"]
    ascom.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
    ascom = type(ascom).objects.get(pk=ascom.pk)  # sem o cache de permissões
    ana = Palestrante.objects.create(nome="Ana", servidor=servidor)
    p = palestras.criar(ascom, {"data_solicitacao": dia, "solicitante": "Escola",
                                "data_inicio_evento": dia, "palestrantes": [ana]})
    # Na palestra: a palestrante (ligada ao servidor) está no ofício.
    avisos = conflitos_palestras.avisos_da_palestra(p)
    assert any(a.documento == f"Ofício {oficio.numero_formatado}" and a.recurso == servidor.nome
               for a in avisos)
    # No ofício: o servidor está na palestra (como palestrante).
    textos = conflitos_viagens.avisos_do_oficio(oficio)
    assert any("como palestrante" in t and f"Palestra #{p.pk}" in t for t in textos)
    # Cancelada não conta.
    palestras.registrar_andamento(ascom, p.pk, "cancelada")
    assert not any("como palestrante" in t for t in conflitos_viagens.avisos_do_oficio(oficio))


def test_pedido_repetido_e_viatura():
    c = cenario_completo()
    op = c.usuarios["operador"]
    op.groups.add(Group.objects.get(name="ASCOM_PALESTRAS"))
    op = type(op).objects.get(pk=op.pk)
    dia = timezone.localdate() + timedelta(days=30)
    from gestao.cadastros.models import Municipio
    m = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                        defaults={"nome": "Curitiba", "uf": "PR"})[0]
    a = palestras.criar(op, {"data_solicitacao": dia, "solicitante": "A", "municipio": m,
                             "data_inicio_evento": dia, "hora_inicio": time(9)})
    b = palestras.criar(op, {"data_solicitacao": dia, "solicitante": "B", "municipio": m,
                             "data_inicio_evento": dia})
    avisos = conflitos_palestras.avisos_da_palestra(b)
    assert [x.tipo for x in avisos] == ["pedido"] and avisos[0].chave == ("palestra", a.pk)
    assert "Já existe pedido" in avisos[0].mensagem
    # Viatura: o mesmo carro em dois ofícios sobrepostos.
    base = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    novo = services.criar_rascunho(op)
    novo = services.salvar_dados(novo, op, {"motivo": "Outra", "viatura": base.viatura})
    services.salvar_trechos(novo, op, [services.TrechoInformado(x.origem_id, x.destino_id,
                                                                x.saida_em, x.chegada_em)
                                       for x in base.trechos.order_by("ordem")])
    textos = conflitos_viagens.avisos_do_oficio(novo)
    assert any(t.startswith(f"Viatura {base.viatura.placa_formatada}") for t in textos)
