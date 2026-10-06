"""CB6a: registrar a entrega (a partir do dia do evento, observação obrigatória com
ocorrência, anexo conferido pelo conteúdo, histórico), o resumo por fornecedor, o painel
(números, alertas, "O que fazer hoje") e o "parada há N dias" da lista."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.cadastros.models import Municipio
from gestao.coffee import entregas, painel, pedidos
from gestao.coffee.models import Contrato, Entrega, Fornecedor, Lote, Movimento, Solicitacao
from gestao.identidade.models import Usuario

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture
def base(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    u = Usuario.objects.create_user("ana", "ana@teste.invalid", None, nome="Ana")
    u.groups.add(Group.objects.get(name="ASCOM_COFFEE_BREAK"))
    hoje = timezone.localdate()
    f = Fornecedor.objects.create(razao_social="Buffet Exemplo Ltda", cnpj="11222333000181")
    c = Contrato.objects.create(fornecedor=f, numero="12/2025", valor_unitario=Decimal("20"),
                                vigencia_fim=hoje + timedelta(days=45))
    curitiba = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                               defaults={"nome": "Curitiba", "uf": "PR"})[0]
    lote = Lote.objects.create(contrato=c, numero=1, exercicio=str(hoje.year),
                               quantidade_total=100)
    lote.municipios.set([curitiba])
    return u, curitiba, hoje, f


def _os(u, municipio, hoje, **campos) -> Solicitacao:
    s = pedidos.salvar(u, {"municipio": municipio, "data_solicitacao": hoje, "numero": "",
                           "descricao": campos.pop("descricao", "Posse"),
                           "quantidade": campos.pop("quantidade", 10)},
                       retroativo=True, justificativa="teste").solicitacao
    if campos:
        Solicitacao.objects.filter(pk=s.pk).update(**campos)
        s.refresh_from_db()
    return s


def test_registrar_entrega_regras_e_historico(base):
    u, mun, hoje, _f = base
    futura = _os(u, mun, hoje, data_evento=hoje + timedelta(days=2))
    with pytest.raises(pedidos.PedidoInvalido, match="a partir do dia do evento"):
        entregas.registrar(u, futura.pk, tipo="sem_ocorrencia", avaliacao=None,
                           recebido_por="", observacao="")
    s = _os(u, mun, hoje, data_evento=hoje)
    with pytest.raises(pedidos.PedidoInvalido, match="Descreva a ocorrência"):
        entregas.registrar(u, s.pk, tipo="atraso", avaliacao=3, recebido_por="", observacao=" ")
    with pytest.raises(pedidos.PedidoInvalido, match="vai de 1 a 5"):
        entregas.registrar(u, s.pk, tipo="sem_ocorrencia", avaliacao=6, recebido_por="",
                           observacao="")
    with pytest.raises(pedidos.PedidoInvalido, match="não corresponde"):
        entregas.registrar(u, s.pk, tipo="sem_ocorrencia", avaliacao=None, recebido_por="",
                           observacao="", anexo=SimpleUploadedFile("foto.png", b"%PDF-1.4 x"))
    e = entregas.registrar(u, s.pk, tipo="atraso", avaliacao=4, recebido_por="Plantão",
                           observacao="Chegou 30 minutos depois.",
                           anexo=SimpleUploadedFile("foto.png", PNG))
    assert e.anexo and entregas.mensagem(e) == "Entrega registrada: Atraso na entrega."
    mov = Movimento.objects.filter(solicitacao=s, acao="entrega").get()
    assert mov.texto == ("Entrega registrada: Atraso na entrega; avaliação 4/5; recebido por "
                         "Plantão. Chegou 30 minutos depois.")
    pedidos.cancelar(u, s.pk, "Evento desmarcado")
    with pytest.raises(pedidos.PedidoInvalido, match="cancelada"):
        entregas.registrar(u, s.pk, tipo="sem_ocorrencia", avaliacao=None, recebido_por="",
                           observacao="")


def test_resumo_por_fornecedor(base):
    u, mun, hoje, f = base
    assert entregas.resumo_do_fornecedor(f.pk).texto == "Nenhuma entrega registrada"
    s = _os(u, mun, hoje, data_evento=hoje)
    entregas.registrar(u, s.pk, tipo="sem_ocorrencia", avaliacao=5, recebido_por="",
                       observacao="")
    entregas.registrar(u, s.pk, tipo="falta_itens", avaliacao=4, recebido_por="",
                       observacao="Faltaram sucos.")
    r = entregas.resumo_do_fornecedor(f.pk)
    assert r.texto == "2 entregas registradas · nota média 4,5 · 1 ocorrência"
    assert r.por_tipo == {"falta_itens": 1}


def test_painel_numeros_alertas_e_grupos(base):
    u, mun, hoje, _f = base
    _os(u, mun, hoje, data_evento=hoje + timedelta(days=3), local_entrega="Auditório",
        horario="09:00")
    parada = _os(u, mun, hoje, data_evento=hoje - timedelta(days=12), quantidade=80)
    Movimento.objects.filter(solicitacao=parada).update(em=timezone.now() - timedelta(days=20))
    _os(u, mun, hoje, nota_fiscal="77", ordem_bancaria_em=hoje, protocolo_pagamento="1")
    p = painel.montar(hoje)
    assert p.indicadores.capacidade == 100 and p.indicadores.consumido == 100
    assert p.indicadores.restante == 0 and p.indicadores.pendencias == 3
    assert p.indicadores.gasto == Decimal("2000.00") and p.indicadores.pago == Decimal("200.00")
    # Evento de 12 dias atrás cai no último mês completo: há ritmo, e o saldo zerado "acaba"
    # hoje, antes do fim do contrato (como na referência).
    assert p.alertas_de_saldo[0].alerta.startswith("No ritmo dos últimos 3 meses (")
    assert "faixa de 60 dias" in p.vigencia[0][1]
    Lote.objects.update(quantidade_total=200)  # cabe mais uma OS, com evento hoje
    hoje_ = _os(u, mun, hoje, quantidade=5)
    Solicitacao.objects.filter(pk=hoje_.pk).update(data_evento=hoje)
    item = next(i for g in painel.o_que_fazer(hoje) if g.chave == "entregas" for i in g.itens
                if i[0].pk == hoje_.pk)
    assert item[2:] == ("Registrar a entrega", "entregas")
    assert p.certidoes and len(p.certidoes[0][1]) == 5  # nenhuma certidão cadastrada
    grupos = {g.chave: g for g in p.grupos}
    assert list(grupos) == ["entregas", "sem_nota", "ob_nao_enviada"]
    assert grupos["sem_nota"].itens[0][1] == 12  # desde o fim do evento, posterior ao histórico
    entrega = grupos["entregas"].itens[0]
    assert entrega[2:] == ("Abrir a OS", "entrega")  # evento futuro: conferir local e quem recebe
    assert grupos["ob_nao_enviada"].itens[0][2] == "Informar o envio da OB"
    assert p.pedem_acao == 3 and p.vigencia[0][2] == "aviso"


def test_tela_do_painel_e_navegacao(base):
    u, mun, hoje, _f = base
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:painel")).content.decode()
    assert "Saldo restante" in html and "Pendências financeiras" in html
    assert "Nada pendente com a equipe" in html  # sem OS: o vazio de "O que fazer hoje"
    assert "Nenhuma solicitação registrada ainda" in html
    s = _os(u, mun, hoje, data_evento=hoje - timedelta(days=1))
    html = cli.get(reverse("coffee:painel")).content.decode()
    assert "Eventos realizados sem nota fiscal" in html and "Anexar a nota" in html
    assert f'{reverse("coffee:solicitacao", args=[s.pk])}#pdfs' in html
    outro = Usuario.objects.create_user("beto", "beto@teste.invalid", None, nome="Beto")
    cli.force_login(outro)
    assert cli.get(reverse("coffee:painel")).status_code == 403


def test_lista_mostra_parada_so_quando_depende_da_equipe(base):
    u, mun, hoje, _f = base
    s = _os(u, mun, hoje, data_evento=hoje - timedelta(days=9), descricao="Formatura")
    Movimento.objects.filter(solicitacao=s).update(em=timezone.now() - timedelta(days=30))
    futura = _os(u, mun, hoje, data_evento=hoje + timedelta(days=30), descricao="Seminário")
    Movimento.objects.filter(solicitacao=futura).update(em=timezone.now() - timedelta(days=30))
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:solicitacoes")).content.decode()
    assert html.count("Parada há") == 1 and "Parada há 9 dias" in html


def test_folha_registra_entrega_e_guarda_o_rascunho(base):
    u, mun, hoje, _f = base
    s = _os(u, mun, hoje, data_evento=hoje)
    cli = Client()
    cli.force_login(u)
    url = reverse("coffee:registrar_entrega", args=[s.pk])
    r = cli.post(url, {"tipo": "qualidade", "recebido_por": "Plantão", "observacao": ""},
                 follow=True)
    html = r.content.decode()
    assert "Descreva a ocorrência" in html and 'aria-invalid="true"' in html
    assert 'value="Plantão"' in html  # o que foi digitado volta
    r = cli.post(url, {"tipo": "sem_ocorrencia", "avaliacao": "5",
                       "anexo": SimpleUploadedFile("foto.png", PNG)}, follow=True)
    html = r.content.decode()
    assert "Entrega registrada: Entregue sem ocorrência." in html and "Avaliação 5/5" in html
    e = Entrega.objects.get(solicitacao=s)
    baixado = cli.get(reverse("coffee:arquivo_entrega", args=[e.pk]))
    assert baixado.status_code == 200 and baixado["Content-Type"] == "image/png"
    futura = _os(u, mun, hoje, data_evento=hoje + timedelta(days=5))
    html = cli.get(reverse("coffee:solicitacao", args=[futura.pk])).content.decode()
    assert "o registro abre no dia do evento" in html and url not in html


def test_entrega_impede_excluir_e_anexo_recusado_aparece_no_campo(base):
    u, mun, hoje, _f = base
    s = _os(u, mun, hoje, data_evento=hoje)
    cli = Client()
    cli.force_login(u)
    url = reverse("coffee:registrar_entrega", args=[s.pk])
    html = cli.post(url, {"tipo": "sem_ocorrencia",
                          "anexo": SimpleUploadedFile("foto.jpg", b"GIF89a....")},
                    follow=True).content.decode()
    assert 'id="erro-anexo"' in html and not Entrega.objects.exists()
    entregas.registrar(u, s.pk, tipo="sem_ocorrencia", avaliacao=None, recebido_por="",
                       observacao="")
    with pytest.raises(pedidos.PedidoInvalido, match="já tem entrega registrada"):
        pedidos.excluir(u, s.pk)


def test_rodape_padrao_da_folha(base):
    """Rodapé igual em toda folha (pedido do usuário, 06/10): Finalizar grava e volta à lista;
    Ações tem Duplicar, Cancelar e Excluir (este só antes do financeiro)."""
    u, mun, hoje, _f = base
    s = _os(u, mun, hoje, data_evento=hoje + timedelta(days=3))
    cli = Client()
    cli.force_login(u)
    html = cli.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Finalizar" in html and "Duplicar OS" in html and "Cancelar OS" in html
    assert "Excluir OS" in html and 'id="duplicar-coffee"' in html
    Solicitacao.objects.filter(pk=s.pk).update(nota_fiscal="1")
    html = cli.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Excluir OS" not in html
