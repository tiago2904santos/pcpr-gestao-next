"""E-mail ao fornecedor: a tela preenchida com a configuração e os dados da OS, os endereços
conferidos, o PDF anexo, o histórico, "OS enviada em" e o envio da OB que conclui o
pagamento quando é o próximo marco."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse

from gestao.coffee import envio_email, vias
from gestao.coffee.models import ConfiguracaoOficio, Movimento, Solicitacao
from gestao.coffee.pedidos import PedidoInvalido

from .test_entregas_painel import _os, base  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def test_enderecos_e_campos():
    assert envio_email.enderecos("a@x.invalid; b@y.invalid, A@x.invalid") == [
        "a@x.invalid", "b@y.invalid"]
    with pytest.raises(ValueError, match="E-mail inválido: nada"):
        envio_email.enderecos("a@x.invalid nada")
    assert envio_email.preencher("OS {numero} {desconhecido}", {"numero": "3/2026"}) == (
        "OS 3/2026 {desconhecido}")


def test_envio_da_os_pela_tela(base, mailoutbox, monkeypatch):  # noqa: F811
    u, curitiba, hoje, fornecedor = base
    fornecedor.email = "pedidos@buffet.invalid"
    fornecedor.save()
    cfg = ConfiguracaoOficio.atual()
    cfg.emails_ascom = "ascom@pcpr.invalid"
    cfg.save()
    s = _os(u, curitiba, hoje, data_evento=hoje + timedelta(days=5), local_entrega="Auditório",
            responsavel="Plantão")
    monkeypatch.setattr(vias, "obter", lambda *a: vias.Arquivo(b"%PDF-1.4", "OS.pdf", False))
    c = Client()
    c.force_login(u)
    url = reverse("coffee:enviar_email", args=[s.pk, "os"])
    html = c.get(url).content.decode()
    assert 'value="pedidos@buffet.invalid"' in html and 'value="ascom@pcpr.invalid"' in html
    assert f"Ordem de Serviço {s.numero}" in html and "Auditório" in html
    r = c.post(url, {"para": "errado", "copia": "", "assunto": "X", "texto": ""})
    assert r.status_code == 422 and "E-mail inválido: errado" in r.content.decode()
    r = c.post(url, {"para": "pedidos@buffet.invalid", "copia": "ascom@pcpr.invalid",
                     "assunto": "OS  para   o evento", "texto": "Segue."})
    assert r.status_code == 302 and r["Location"].endswith("#documentos")
    assert len(mailoutbox) == 1
    m = mailoutbox[0]
    assert m.to == ["pedidos@buffet.invalid"] and m.cc == ["ascom@pcpr.invalid"]
    assert m.subject == "OS para o evento" and m.attachments[0][0] == "OS.pdf"
    s.refresh_from_db()
    assert s.os_enviada_em is not None
    assert Movimento.objects.filter(solicitacao=s, acao="email",
                                    texto__contains="pedidos@buffet.invalid").exists()
    assert "Reenviar" in c.get(url).content.decode()


def test_ob_conclui_o_pagamento(base, mailoutbox):  # noqa: F811
    u, curitiba, hoje, _f = base
    s = _os(u, curitiba, hoje, data_evento=hoje - timedelta(days=10), nota_fiscal="123",
            protocolo_pagamento="12.345.678-9", atesto_em=hoje - timedelta(days=5),
            ordem_bancaria_em=hoje - timedelta(days=2))
    with pytest.raises(PedidoInvalido, match="PDF da ordem bancária"):
        envio_email.enviar(u, s.pk, "ob", para="f@x.invalid", copia="", assunto="OB", texto="")
    s.ob_pdf.save("ob.pdf", ContentFile(b"%PDF-1.4"), save=True)
    with pytest.raises(PedidoInvalido, match="Informe o assunto"):
        envio_email.enviar(u, s.pk, "ob", para="f@x.invalid", copia="", assunto=" ", texto="")
    feita = envio_email.enviar(u, s.pk, "ob", para="f@x.invalid", copia="", assunto="OB",
                               texto="Pago.", hoje=hoje)
    assert feita.envio_empresa_em == hoje and feita.concluida
    assert mailoutbox[0].attachments[0][2] == "application/pdf"
    assert Solicitacao.objects.get(pk=s.pk).movimentos.filter(acao="email").count() == 1
