"""Preencher a solicitação nova com um e-mail: a leitura (período com o trecho, tipo por
sinônimo sem confundir dia da semana, município, rótulos, serviços sem os negados, unidade
móvel) e a tela (texto colado ou .eml; nada grava)."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Municipio
from gestao.eventos import leitura_email
from gestao.eventos.models import Servico, Solicitacao

from .test_solicitacoes import _usuario

EMAIL = """De: Maria Silva <maria.silva@escola.invalid>
Enviado em: terça-feira, 6 de outubro de 2026 10:42
Assunto: RES: Pedido de ação na Feira de Saúde

Bom dia,

Pedimos a presença da Polícia Civil na Feira de Saúde da escola, nos dias 20 e 21 de
novembro, em Ponta Grossa, com emissão de RG e coleta de digitais. Não precisamos de foto.
Local: Colégio Estadual Central
Endereço: Rua das Flores, 100
CEP 84010-000
Esperamos cerca de 150 atendimentos. Se possível, enviar a unidade móvel.

Atenciosamente,
Maria Silva
Diretora
(42) 99999-1111
"""


def test_leitura_do_pedido():
    lido = leitura_email.ler(
        EMAIL, date(2026, 10, 17), tipos={"feira", "evento", "palestra"},
        municipios={"ponta grossa": "Ponta Grossa/PR", "curitiba": "Curitiba/PR"},
        nomes_servicos={"emissao de cin", "coleta de digitais", "fotografia para documento"})
    assert lido.periodo and (lido.periodo.inicio, lido.periodo.fim) == (
        date(2026, 11, 20), date(2026, 11, 21))
    assert lido.periodo.trecho.startswith("20 e 21 de")
    assert lido.tipo == "feira" and lido.municipio == "ponta grossa"
    assert lido.local == "Colégio Estadual Central" and lido.cep == "84010-000"
    assert (lido.solicitante, lido.cargo, lido.contato) == ("Maria Silva", "Diretora",
                                                            "(42) 99999-1111")
    assert lido.servicos == ["emissao de cin", "coleta de digitais"]  # a foto foi negada
    assert lido.quantidade_cin == 150 and lido.unidade_movel
    assert lido.descricao.endswith("Origem: e-mail de Maria Silva <maria.silva@escola.invalid>"
                                   " em 06/10/2026 10:42")


def test_periodos_e_tipos():
    hoje = date(2026, 10, 17)
    p = leitura_email.periodo("evento de 10 a 12/11", hoje)
    assert p and (p.inicio, p.fim) == (date(2026, 11, 10), date(2026, 11, 12))
    p = leitura_email.periodo("nos dias 3, 4 e 5 de dezembro de 2026", hoje)
    assert p and (p.inicio, p.fim) == (date(2026, 12, 3), date(2026, 12, 5))
    assert leitura_email.periodo("sem data nenhuma", hoje) is None
    tipos = {"feira", "inauguracao/solenidade", "capacitacao", "evento"}
    assert leitura_email.tipo("Na quinta-feira teremos a formatura", tipos) == (
        "inauguracao/solenidade")
    assert leitura_email.tipo("Um curso de primeiros socorros", tipos) == "capacitacao"
    assert leitura_email.tipo("Uma ação na praça", tipos) == "evento"


@pytest.mark.django_db
def test_tela_preenche_sem_gravar():
    Municipio.objects.get_or_create(codigo_ibge="4119905",
                                    defaults={"nome": "Ponta Grossa", "uf": "PR"})
    c = Client()
    c.force_login(_usuario("ana"))
    r = c.post(reverse("eventos:preencher"), {"email": EMAIL})
    html = r.content.decode()
    assert r.status_code == 200 and "Preenchido com o e-mail" in html
    assert 'value="Ponta Grossa/PR"' in html and 'value="Colégio Estadual Central"' in html
    cin = Servico.objects.get(codigo="CIN")  # a atividade do catálogo compartilhado
    assert f'name="servico_{cin.pk}" value="1" form="form-solicitacao" checked' in html
    assert not Solicitacao.objects.exists()
    eml = SimpleUploadedFile("pedido.eml", (
        b"From: Maria Silva <maria.silva@escola.invalid>\r\n"
        b"Date: Tue, 06 Oct 2026 10:42:00 -0300\r\nSubject: Feira de Saude\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Feira em Ponta Grossa no dia 20/11.\r\n"), content_type="message/rfc822")
    html = c.post(reverse("eventos:preencher"), {"arquivo": eml}).content.decode()
    assert "20/11/2026" in html and "Maria Silva" in html
    r = c.post(reverse("eventos:preencher"), {"arquivo": SimpleUploadedFile("x.pdf", b"%PDF")})
    assert r.status_code == 302


@pytest.mark.django_db
def test_eml_com_cabecalho_gigante_e_recusado_sem_parse():
    c = Client()
    c.force_login(_usuario("bia"))
    bomba = (b"From: a@b.invalid\r\nSubject: " + b" ".join([b"=?utf-8?q?a?="] * 20000)
             + b"\r\n\r\ncorpo")
    r = c.post(reverse("eventos:preencher"),
               {"arquivo": SimpleUploadedFile("x.eml", bomba, content_type="message/rfc822")},
               follow=True)
    assert "Envie o e-mail salvo como .eml (até 512 KB)" in r.content.decode()
