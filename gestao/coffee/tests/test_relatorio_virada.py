"""CB6b: o relatório do contrato (consumo por mês e município, lotes, saldo dos vigentes,
ritmo e projeção, valores, prazo nota → OB, entregas; tela, CSV e PDF) e a virada de
exercício (cópia dos lotes vigentes com quantidade e empenho, impedimentos, encerrar)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import entregas, pedidos, relatorio, virada
from gestao.coffee.models import Contrato, Fornecedor, Lote, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db


def _usuario(login: str, *papeis: str) -> Usuario:
    u = Usuario.objects.create_user(login, f"{login}@teste.invalid", None, nome=login.title())
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    return u


def _municipio(ibge: str, nome: str) -> Municipio:
    return Municipio.objects.get_or_create(codigo_ibge=ibge, defaults={"nome": nome,
                                                                       "uf": "PR"})[0]


@pytest.fixture
def contrato(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = _usuario("ana", "ASCOM_COFFEE_BREAK")
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=200))
    cwb, sjp = _municipio("4106902", "Curitiba"), _municipio("4125506", "São José dos Pinhais")
    antigo = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year - 1),
                                 quantidade_total=50, ativo=False)
    antigo.municipios.set([cwb])
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=500, empenho="2026NE1",
                               valor_empenho=Decimal("5000.00"), orientacoes="30 min antes",
                               municipios_texto="Curitiba, São José dos Pinhais")
    lote.municipios.set([cwb, sjp])
    return u, c, lote, cwb, sjp, hoje


def _os(u, municipio, hoje, quantidade, **campos) -> Solicitacao:
    s = pedidos.salvar(u, {"municipio": municipio, "data_solicitacao": hoje, "numero": "",
                           "descricao": "Evento", "quantidade": quantidade}).solicitacao
    if campos:
        Solicitacao.objects.filter(pk=s.pk).update(**campos)
        s.refresh_from_db()
    return s


def test_relatorio_numeros(contrato):
    u, c, _lote, cwb, sjp, hoje = contrato
    mes_passado = (hoje.replace(day=1) - timedelta(days=1)).replace(day=10)
    a = _os(u, cwb, hoje, 60, data_evento=mes_passado, nota_emissao=mes_passado,
            ordem_bancaria_em=mes_passado + timedelta(days=12))
    _os(u, sjp, hoje, 30, data_evento=mes_passado, data_oficio=mes_passado,
        ordem_bancaria_em=mes_passado + timedelta(days=8))
    _os(u, cwb, hoje, 90, data_evento=hoje)
    pedidos.cancelar(u, _os(u, cwb, hoje, 40).pk, "Desmarcado")
    entregas.registrar(u, a.pk, tipo="atraso", avaliacao=3, recebido_por="",
                       observacao="Atrasou.")
    r = relatorio.montar(c, hoje)
    assert [(m.os, m.quantidade, m.barra) for m in r.meses] == [(2, 90, 100), (1, 90, 100)]
    assert r.meses[0].valor == Decimal("1800.00")
    assert [(mu.nome, mu.quantidade) for mu in r.municipios] == [("Curitiba", 150),
                                                                 ("São José dos Pinhais", 30)]
    assert r.capacidade == 500 and r.restante == 320 and r.consumido == 180  # só o vigente
    assert r.ritmo == 30.0  # 90 no último mês completo ÷ 3
    assert r.acaba_em == hoje + timedelta(days=round(320 / 30 * 30.44))
    assert r.gasto == Decimal("3600.00") and r.pago == Decimal("1800.00")
    assert r.empenhado == Decimal("5000.00") and r.saldo_empenho == Decimal("1400.00")
    assert r.prazo_medio == 10 and r.pagamentos_medidos == 2
    assert r.entregas.texto == "1 entrega registrada · nota média 3,0 · 1 ocorrência"
    assert [linha.lote.exercicio for linha in r.lotes] == [str(hoje.year), str(hoje.year - 1)]
    linhas = list(relatorio.linhas_csv(r))
    assert linhas[0] == ["Relatório do contrato", "12/2025", "Buffet Exemplo Ltda"]
    assert ["Valor gasto", "3600,00"] in linhas and ["Saldo do empenho", "1400,00"] in linhas


def test_telas_do_relatorio(contrato):
    u, c, _lote, cwb, _sjp, hoje = contrato
    _os(u, cwb, hoje, 10, data_evento=hoje)
    cli = Client()
    cli.force_login(u)
    url = reverse("coffee:relatorio_contrato", args=[c.pk])
    html = cli.get(url).content.decode()
    assert "Relatório do contrato 12/2025" in html and "Consumo por município" in html
    csv = cli.get(url + "?formato=csv")
    assert csv["Content-Type"].startswith("text/csv") and csv.content.startswith(b"\xef\xbb\xbf")
    assert "Relatorio do contrato 12-2025.csv" in csv["Content-Disposition"]
    pdf = cli.get(url + "?formato=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert url in cli.get(reverse("coffee:lotes")).content.decode()  # link em cada lote
    cli.force_login(_usuario("beto"))
    assert cli.get(url).status_code == 403


def test_virada_regras(contrato):
    u, c, lote, _cwb, _sjp, hoje = contrato
    destino = hoje.year + 1
    assert virada.exercicio_de_origem() == hoje.year
    assert virada.impedimento(lote, destino) == ""
    c.vigencia_fim = date(destino, 3, 31)
    c.save()
    assert virada.aviso_de_vigencia(lote, destino) == (
        f"O contrato vai até 31/03/{destino}: o lote de {destino} só cobre eventos até lá.")
    c.vigencia_fim = date(hoje.year, 12, 30)
    c.save()
    assert virada.impedimento(lote, destino) == (
        f"Contrato vencido em 30/12/{hoje.year}: providencie o aditivo de prorrogação antes.")
    admin = _usuario("adm", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR")
    with pytest.raises(virada.ViradaInvalida, match="Corrija"):
        virada.abrir_exercicio(admin, destino, [virada.Linha(lote, True, 400)], False)
    with pytest.raises(virada.ViradaInvalida, match="Marque ao menos"):
        virada.abrir_exercicio(admin, destino, [virada.Linha(lote, False, 400)], False)
    from django.core.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        virada.abrir_exercicio(u, destino, [virada.Linha(lote, True, 400)], False)


def test_virada_pela_tela(contrato):
    u, _c, lote, cwb, sjp, hoje = contrato
    destino = hoje.year + 1
    admin = _usuario("adm", "ASCOM_COFFEE_BREAK", "ADMINISTRADOR")
    cli = Client()
    cli.force_login(u)
    assert cli.get(reverse("coffee:virada")).status_code == 403
    cli.force_login(admin)
    url = reverse("coffee:virada")
    assert f"Abrir o exercício {destino}" in cli.get(url).content.decode()
    assert f"Abrir exercício {destino}" in cli.get(reverse("coffee:lotes")).content.decode()
    r = cli.post(url, {"criar": [str(lote.pk)], f"quantidade-{lote.pk}": ""})
    assert r.status_code == 422 and "Informe a quantidade do novo exercício." in r.content.decode()
    r = cli.post(url, {"criar": [str(lote.pk)], f"quantidade-{lote.pk}": "600",
                       f"empenho-{lote.pk}": "2027NE9", f"valor-{lote.pk}": "6.000,50",
                       "encerrar": "1"}, follow=True)
    assert (f"Exercício {destino} aberto: 1 lote criado com os municípios, orientações e "
            f"especificações de {hoje.year}. Os lotes de {hoje.year} copiados foram "
            "encerrados.") in r.content.decode()
    novo = Lote.objects.get(exercicio=str(destino))
    assert novo.quantidade_total == 600 and novo.empenho == "2027NE9"
    assert novo.valor_empenho == Decimal("6000.50") and novo.orientacoes == "30 min antes"
    assert set(novo.municipios.all()) == {cwb, sjp}
    assert novo.observacoes == f"Aberto na virada do exercício a partir do Lote 1 ({hoje.year})."
    lote.refresh_from_db()
    assert not lote.ativo
    assert virada.impedimento(lote, destino) == f"O Lote 1 ({destino}) deste contrato já existe."
