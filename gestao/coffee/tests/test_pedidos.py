"""CB2: a solicitação de coffee break, etapa 1 — lote pelo município (e pela cidade mais
perto), saldo com trava e mensagens, valor unitário congelado, vigência, retroativo,
antecedência, número da OS, cancelar/reativar/excluir, duplicar, lista com a situação,
CSV, o trecho do lote e a lista de lotes."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import pedidos, queries
from gestao.coffee.models import Contrato, Fornecedor, Lote, Movimento, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _municipio(nome: str, ibge: str, lat: str, lon: str, uf: str = "PR") -> Municipio:
    m, _ = Municipio.objects.get_or_create(codigo_ibge=ibge, defaults={"nome": nome, "uf": uf})
    Municipio.objects.filter(pk=m.pk).update(latitude=Decimal(lat), longitude=Decimal(lon))
    m.refresh_from_db()
    return m


@pytest.fixture
def cenario():
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Teste Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="10/2025", valor_unitario=Decimal("21.07"),
                                vigencia_fim=hoje + timedelta(days=200),
                                antecedencia_minima_dias=2)
    curitiba = _municipio("Curitiba", "4106902", "-25.4284", "-49.2733")
    pinhais = _municipio("Pinhais", "4119152", "-25.4429", "-49.1927")
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=100)
    lote.municipios.set([curitiba])
    return {"u": u, "hoje": hoje, "contrato": c, "lote": lote, "curitiba": curitiba,
            "pinhais": pinhais}


def _dados(cen, **extra) -> dict:
    hoje = cen["hoje"]
    return {"municipio": cen["curitiba"], "data_solicitacao": hoje, "numero": "",
            "descricao": "Reunião  com\nlideranças", "quantidade": 40,
            "data_evento": hoje + timedelta(days=10), **extra}


def test_registra_no_lote_do_municipio_com_preco_congelado(cenario):
    r = pedidos.salvar(cenario["u"], _dados(cenario))
    s = r.solicitacao
    assert s.lote == cenario["lote"] and s.valor_unitario == Decimal("21.0700")
    assert s.descricao == "Reunião com lideranças" and s.numero == f"1/{cenario['hoje'].year}"
    assert s.valor == Decimal("842.80") and s.situacao == "aguardando_nota"
    assert Movimento.objects.get(solicitacao=s).texto.startswith(
        f"Solicitação 1/{cenario['hoje'].year} registrada no Lote 1")
    cenario["contrato"].valor_unitario = Decimal("30")
    cenario["contrato"].save()
    s2 = pedidos.salvar(cenario["u"], _dados(cenario, descricao="Outra"), s).solicitacao
    assert s2.valor_unitario == Decimal("21.0700")  # não muda sem troca de lote


def test_cidade_mais_perto_e_nenhum_lote(cenario):
    s = pedidos.salvar(cenario["u"], _dados(cenario, municipio=cenario["pinhais"])).solicitacao
    assert s.lote == cenario["lote"]  # Pinhais não está no lote; Curitiba é a mais perto
    info = queries.lote_para(cenario["pinhais"], cenario["hoje"])
    assert info is not None and info.proximidade.startswith("Curitiba, a ")
    Lote.objects.update(ativo=False)
    with pytest.raises(pedidos.PedidoInvalido, match="Nenhum lote ativo atende Curitiba/PR"):
        pedidos.salvar(cenario["u"], _dados(cenario))


def test_saldo_com_faturada_cancelar_e_reativar(cenario):
    u = cenario["u"]
    a = pedidos.salvar(u, _dados(cenario, quantidade=60)).solicitacao
    with pytest.raises(pedidos.PedidoInvalido, match="restam 40 de 100 unidades"):
        pedidos.salvar(u, _dados(cenario, quantidade=50))
    b = pedidos.salvar(u, _dados(cenario, quantidade=40)).solicitacao
    Solicitacao.objects.filter(pk=a.pk).update(quantidade_faturada=50)  # nota faturou menos
    assert queries.saldo(cenario["lote"]).restante == 10
    pedidos.cancelar(u, b.pk, "Evento adiado")
    assert queries.saldo(cenario["lote"]).restante == 50
    with pytest.raises(pedidos.PedidoInvalido, match="já está cancelada"):
        pedidos.cancelar(u, b.pk, "de novo")
    pedidos.salvar(u, _dados(cenario, quantidade=45))
    with pytest.raises(pedidos.PedidoInvalido, match="restam 5 de 100"):
        pedidos.reativar(u, b.pk)
    with pytest.raises(pedidos.PedidoInvalido, match="Informe o motivo"):
        pedidos.cancelar(u, a.pk, " ")


def test_vigencia_retroativo_e_antecedencia(cenario):
    u, hoje = cenario["u"], cenario["hoje"]
    with pytest.raises(pedidos.PedidoInvalido, match="Contrato vencido em"):
        pedidos.salvar(u, _dados(cenario, data_evento=hoje + timedelta(days=400)))
    with pytest.raises(pedidos.PedidoInvalido, match="registro retroativo"):
        pedidos.salvar(u, _dados(cenario, data_evento=hoje - timedelta(days=3)))
    r = pedidos.salvar(u, _dados(cenario, data_evento=hoje - timedelta(days=3)),
                       retroativo=True, justificativa="Pedido feito por telefone")
    assert r.solicitacao.movimentos.filter(texto__startswith="Registro retroativo").exists()
    r = pedidos.salvar(u, _dados(cenario, data_evento=hoje + timedelta(days=1)))
    assert "amanhã" in r.aviso and "2 dias de antecedência" in r.aviso


def test_numero_da_os_digitado_repetido_e_proximo(cenario):
    u, ano = cenario["u"], cenario["hoje"].year
    a = pedidos.salvar(u, _dados(cenario, numero="41")).solicitacao
    assert a.numero == f"41/{ano}" and queries.proximo_numero(ano) == f"42/{ano}"
    with pytest.raises(pedidos.PedidoInvalido, match=f"A OS 41/{ano} já existe"):
        pedidos.salvar(u, _dados(cenario, numero="41"))
    with pytest.raises(pedidos.PedidoInvalido, match="1 ou mais"):
        pedidos.salvar(u, _dados(cenario, numero="0"))


def test_excluir_so_antes_do_financeiro_e_bloqueio(cenario):
    u = cenario["u"]
    a = pedidos.salvar(u, _dados(cenario)).solicitacao
    Solicitacao.objects.filter(pk=a.pk).update(nota_fiscal="8957")
    with pytest.raises(pedidos.PedidoInvalido, match="já tem nota ou protocolo"):
        pedidos.excluir(u, a.pk)
    b = pedidos.salvar(u, _dados(cenario, quantidade=5)).solicitacao
    assert pedidos.excluir(u, b.pk) == b.numero
    Solicitacao.objects.filter(pk=a.pk).update(
        protocolo_pagamento="12.345.678-9", atesto_em=date(2026, 1, 2),
        ordem_bancaria_em=date(2026, 1, 3), envio_empresa_em=date(2026, 1, 4))
    a.refresh_from_db()
    assert a.situacao == "concluida" and a.bloqueada
    with pytest.raises(pedidos.PedidoInvalido, match="fluxo financeiro concluído"):
        pedidos.cancelar(u, a.pk, "x")


def _cliente(u) -> Client:
    c = Client()
    c.force_login(u)
    return c


def test_telas_lista_folha_lote_csv_e_permissao(cenario):
    u, hoje = cenario["u"], cenario["hoje"]
    c = _cliente(u)
    r = c.post(reverse("coffee:nova"), {
        "municipio": "Curitiba/PR", "data_solicitacao": f"{hoje:%d/%m/%Y}",
        "descricao": "Posse da diretoria", "quantidade": "30",
        "data_evento": f"{hoje + timedelta(days=5):%d/%m/%Y}", "cep": "80000000"})
    assert r.status_code == 302
    s = Solicitacao.objects.get()
    assert s.cep == "80000-000"
    html = c.get(reverse("coffee:solicitacoes")).content.decode()
    assert "Posse da diretoria" in html and "Aguardando nota fiscal" in html
    html = c.get(reverse("coffee:solicitacoes"), {"situacao": "cancelada"}).content.decode()
    assert "Posse da diretoria" not in html
    html = c.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "70 de 100 unidades" in html and "Situação da solicitação" in html
    parcial = c.get(reverse("coffee:lote_do_municipio"), {"municipio": "Pinhais/PR"})
    assert "pela cidade mais perto: Curitiba" in parcial.content.decode()
    parcial = c.get(reverse("coffee:lote_do_municipio"), {"municipio": "Santos/SP"})
    assert parcial.status_code == 200
    r = c.get(reverse("coffee:exportar"))
    linhas = list(csv.reader(io.StringIO(r.content.decode().lstrip("﻿")), delimiter=";"))
    assert linhas[0][0] == "Nº" and len(linhas[0]) == 21 and linhas[1][13] == "632,10"
    html = c.get(reverse("coffee:nova"), {"duplicar": s.pk}).content.decode()
    assert "Posse da diretoria" in html and "Copiada de" in html
    assert c.get(reverse("coffee:lotes")).status_code == 200
    r = c.post(reverse("coffee:nova"), {"municipio": "Curitiba/PR",
                                        "data_solicitacao": f"{hoje:%d/%m/%Y}",
                                        "descricao": "x", "quantidade": "0"})
    assert r.status_code == 422 and "pelo menos 1 unidade" in r.content.decode()
    estranho = Usuario.objects.create_user("bia", "bia@teste.invalid", None, nome="Bia")
    assert _cliente(estranho).get(reverse("coffee:solicitacoes")).status_code == 403


def test_folha_travada_com_financeiro_e_versao(cenario):
    u, hoje = cenario["u"], cenario["hoje"]
    s = pedidos.salvar(u, _dados(cenario)).solicitacao
    Solicitacao.objects.filter(pk=s.pk).update(nota_fiscal="1")
    s.refresh_from_db()
    c = _cliente(u)
    html = c.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "foram bloqueados porque a nota fiscal" in html
    from gestao.coffee.forms_pedido import versao_de
    r = c.post(reverse("coffee:solicitacao", args=[s.pk]), {
        "versao": versao_de(s), "municipio": "Pinhais/PR", "quantidade": "99",
        "data_solicitacao": f"{hoje:%d/%m/%Y}", "descricao": "mudou",
        "local_entrega": "Auditório"})
    assert r.status_code == 302
    s.refresh_from_db()
    assert s.local_entrega == "Auditório" and s.quantidade == 40 and s.descricao != "mudou"
    r = c.post(reverse("coffee:solicitacao", args=[s.pk]), {
        "versao": "2020", "local_entrega": "x"})
    assert "alterada por outra pessoa" in r.content.decode()
