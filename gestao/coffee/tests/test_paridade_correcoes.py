"""Correções da auditoria de paridade com a referência (matriz CB-F*): o ano do número da OS
na edição (F26), "parada há" com evento futuro (F94), `{local}` com o endereço (F97), as vias
do ofício na OS principal do pagamento conjunto (F64), a corrida ao salvar a configuração
(F14) e o protocolo do ofício que vira o de pagamento (F52)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.coffee import conjunto, envio_email, financeiro, pedidos, services, vias
from gestao.coffee.dominio_painel import dias_parada
from gestao.coffee.forms import versao_de
from gestao.coffee.models import ConfiguracaoOficio, Solicitacao, Via
from gestao.identidade.models import Usuario

from .test_documentos import os_  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def _dados(s: Solicitacao, **extra) -> dict:
    return {"municipio": s.municipio, "data_solicitacao": s.data_solicitacao,
            "numero": s.numero, "descricao": s.descricao, "quantidade": s.quantidade,
            "data_evento": s.data_evento, **extra}


def _fin(s: Solicitacao, **dados) -> dict:
    s.refresh_from_db()
    return {**{c: getattr(s, c) for c in financeiro.CAMPOS}, **dados}


def test_editar_mantem_o_ano_do_numero(os_):  # noqa: F811
    u, s = os_
    ano = s.data_solicitacao.year
    Solicitacao.objects.filter(pk=s.pk).update(numero=f"5/{ano - 1}")
    s.refresh_from_db()
    # A tela mostra só "5": salvar não troca o ano pelo da data da solicitação.
    pedidos.salvar(u, _dados(s, numero="5", descricao="Posse (ajustada)"), s)
    s.refresh_from_db()
    assert s.numero == f"5/{ano - 1}" and s.descricao == "Posse (ajustada)"


def test_parada_nao_zera_com_evento_futuro():
    hoje = date(2026, 10, 17)
    assert dias_parada(hoje - timedelta(days=10), hoje + timedelta(days=5), hoje) == 10
    assert dias_parada(hoje - timedelta(days=10), hoje - timedelta(days=3), hoje) == 3
    assert dias_parada(hoje - timedelta(days=2), hoje - timedelta(days=9), hoje) == 2
    assert dias_parada(hoje - timedelta(days=4), None, hoje) == 4


def test_local_do_email_leva_o_endereco(os_):  # noqa: F811
    _u, s = os_
    assert envio_email.valores(s)["local"] == "a combinar"
    Solicitacao.objects.filter(pk=s.pk).update(
        local_entrega="Auditório", endereco="Rua Exemplo, 300", bairro="Centro", cep="80000-000")
    s.refresh_from_db()
    assert envio_email.valores(s)["local"] == ("Auditório — Rua Exemplo, 300, Centro, "
                                               "CEP 80000-000")
    Solicitacao.objects.filter(pk=s.pk).update(numero="")
    s.refresh_from_db()
    assert envio_email.valores(s)["numero"] == f"#{s.pk}"


def test_vias_do_oficio_ficam_na_principal(os_):  # noqa: F811
    u, a = os_
    b = pedidos.salvar(u, {"municipio": a.municipio, "data_solicitacao": a.data_solicitacao,
                           "numero": "", "descricao": "Reunião", "quantidade": 21}).solicitacao
    conjunto.definir(u, a.pk, [b.pk])
    for x, nota in ((b, "8952"), (a, "8950")):
        financeiro.salvar_financeiro(u, x.pk, _fin(x, nota_fiscal=nota))
    a.refresh_from_db()
    b.refresh_from_db()
    vias.obter(u, a, "oficio")
    vias.obter(u, b, "oficio")  # mesma folha, pela outra OS: não duplica
    assert Via.objects.filter(tipo="oficio").count() == 1
    assert Via.objects.get(tipo="oficio").solicitacao_id == a.pk
    # O assinado anexado pela outra OS vale para as duas.
    vias.anexar_assinada(u, b.pk, "oficio", SimpleUploadedFile("o.pdf", b"%PDF-1.4 assinado"))
    assert vias.obter(u, a, "oficio").assinada and vias.obter(u, b, "oficio").assinada
    c = Client()
    c.force_login(u)
    folha = c.get(reverse("coffee:solicitacao", args=[b.pk])).content.decode()
    assinada = Via.objects.get(tipo="oficio", assinada=True)
    assert assinada.solicitacao_id == a.pk
    url = reverse("coffee:arquivo_via", args=[b.pk, assinada.pk])
    assert url in folha and c.get(url).status_code == 200
    os_de_a = Via.objects.filter(solicitacao=a, tipo="oficio").exclude(pk=assinada.pk).first()
    outra = Via.objects.create(solicitacao=a, tipo="os", nome="x.pdf", sha256="0" * 64,
                               emitida_por=u, arquivo=os_de_a.arquivo.name)
    assert c.get(reverse("coffee:arquivo_via", args=[b.pk, outra.pk])).status_code == 404


def test_configuracao_salva_por_outra_pessoa_nao_da_erro_500(monkeypatch):
    admin = Usuario.objects.create_user("adm", "adm@teste.invalid", None, nome="Adm")
    for papel in ("ASCOM_COFFEE_BREAK", "ADMINISTRADOR"):
        admin.groups.add(Group.objects.get(name=papel))
    c = Client()
    c.force_login(admin)
    cfg = ConfiguracaoOficio.atual()

    def corrida(*_a, **_k):  # gravou entre a validação e a trava
        raise services.CadastroEmUso("Este cadastro foi alterado por outra pessoa.")

    monkeypatch.setattr(services, "_conferir_versao", corrida)
    r = c.post(reverse("coffee:configuracao"),
               {"versao": versao_de(cfg), "destino_despacho": "Ao GAF,"})
    assert r.status_code == 422 and "alterado por outra pessoa" in r.content.decode()


def test_protocolo_do_oficio_vira_o_de_pagamento(os_):  # noqa: F811
    u, s = os_
    # Sem nota, nada muda; o número interno da PCPR também não conta.
    financeiro.salvar_financeiro(u, s.pk, _fin(s, protocolo_pcpr="12.345.678-9"))
    s.refresh_from_db()
    assert s.protocolo_pagamento == ""
    financeiro.salvar_financeiro(u, s.pk, _fin(s, nota_fiscal="8957",
                                               protocolo_pcpr="2026.050880.000"))
    s.refresh_from_db()
    assert s.protocolo_pagamento == ""
    financeiro.salvar_financeiro(u, s.pk, _fin(s, protocolo_pcpr="123456789"))
    s.refresh_from_db()
    assert s.protocolo_pagamento == "12.345.678-9"
    # O de pagamento mexido à mão não volta a ser o do ofício.
    financeiro.salvar_financeiro(u, s.pk, _fin(s, protocolo_pagamento="98.765.432-1"))
    s.refresh_from_db()
    assert s.protocolo_pagamento == "98.765.432-1"
