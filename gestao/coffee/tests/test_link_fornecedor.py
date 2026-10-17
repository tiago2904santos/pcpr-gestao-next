"""Link do fornecedor: nasce no envio do e-mail (o token só no e-mail; o banco guarda o hash),
a página pública sem login (mesma resposta para token desconhecido, vencido ou revogado),
o envio de certidão conferido e lido, a substituição do pendente, a conferência da equipe
(aceitar entra nas certidões; recusar deixa mandar de novo) e a revogação."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from gestao.coffee import envio_email, link_fornecedor
from gestao.coffee.models import Certidao, EnvioFornecedor, LinkFornecedor

from .test_certidoes import _pdf
from .test_entregas_painel import _os, base  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def _token(mailoutbox) -> str:
    m = re.search(r"/fornecedor/([\w-]+)/", mailoutbox[-1].body)
    assert m
    return m.group(1)


def _certidao(validade):
    return _pdf("CERTIDÃO NEGATIVA DE DÉBITOS TRABALHISTAS CNPJ 11.222.333/0001-81 "
                f"Válida até {validade:%d/%m/%Y}")


def test_link_pelo_email_e_pagina_publica(base, mailoutbox):  # noqa: F811
    u, curitiba, hoje, _f = base
    s = _os(u, curitiba, hoje, data_evento=hoje + timedelta(days=5))
    envio_email.enviar(u, s.pk, "link", para="f@x.invalid", copia="",
                       assunto="Link", texto="Envie por aqui: {link} (até {validade}).")
    token = _token(mailoutbox)
    link = LinkFornecedor.objects.get()
    assert link.token_hash != token and len(link.token_hash) == 64
    assert token in mailoutbox[-1].body and "{link}" not in mailoutbox[-1].body
    anonimo = Client()
    r = anonimo.get(reverse("fornecedor:envio", args=[token]))
    html = r.content.decode()
    assert r.status_code == 200 and "Envio da nota fiscal e das certidões" in html
    assert r["Referrer-Policy"] == "no-referrer" and "noindex" in r["X-Robots-Tag"]
    assert token not in html.replace(reverse("fornecedor:envio", args=[token]), "")
    assert u.nome not in html  # nada da equipe
    for ruim in ("curto", "x" * 40):
        assert anonimo.get(reverse("fornecedor:envio", args=[ruim])).status_code == 404
    # Um link novo revoga o anterior.
    envio_email.enviar(u, s.pk, "link", para="f@x.invalid", copia="", assunto="Link",
                       texto="Sem o campo")
    novo = _token(mailoutbox)
    assert mailoutbox[-1].body.rstrip().endswith(novo + "/")  # sem {link}, vai no fim
    assert anonimo.get(reverse("fornecedor:envio", args=[token])).status_code == 404
    assert anonimo.get(reverse("fornecedor:envio", args=[novo])).status_code == 200


def test_certidao_pelo_link_e_conferencia(base, mailoutbox):  # noqa: F811
    u, curitiba, hoje, fornecedor = base
    s = _os(u, curitiba, hoje, data_evento=hoje + timedelta(days=5))
    envio_email.enviar(u, s.pk, "link", para="f@x.invalid", copia="", assunto="Link",
                       texto="{link}")
    token = _token(mailoutbox)
    anonimo = Client()
    url = reverse("fornecedor:envio", args=[token])
    vencida = anonimo.post(url, {"tipo": "certidao", "tipo_certidao": "trabalhista",
                                 "arquivo": _certidao(hoje - timedelta(days=1))})
    assert vencida.status_code == 422 and "venceu em" in vencida.content.decode()
    r = anonimo.post(url, {"tipo": "certidao", "tipo_certidao": "trabalhista",
                           "arquivo": _certidao(hoje + timedelta(days=90))}, follow=True)
    assert "Certidão Trabalhista recebida. A ASCOM vai conferir." in r.content.decode()
    anonimo.post(url, {"tipo": "certidao", "tipo_certidao": "trabalhista",
                       "arquivo": _certidao(hoje + timedelta(days=100))})
    envios = list(EnvioFornecedor.objects.order_by("pk"))
    assert [e.situacao for e in envios] == ["recusado", "recebido"]  # o novo substitui
    c = Client()
    c.force_login(u)
    folha = c.get(reverse("coffee:solicitacao", args=[s.pk])).content.decode()
    assert "Aguardando conferência" in folha
    r = c.post(reverse("coffee:conferir_envio", args=[s.pk, envios[1].pk]),
               {"acao": "aceitar"}, follow=True)
    assert "Certidão Trabalhista aceita." in r.content.decode()
    assert Certidao.objects.get(fornecedor=fornecedor).validade == hoje + timedelta(days=100)
    r = c.post(reverse("coffee:conferir_envio", args=[s.pk, envios[1].pk]),
               {"acao": "recusar"}, follow=True)
    assert "Este envio já foi conferido." in r.content.decode()
    c.post(reverse("coffee:revogar_link", args=[s.pk]))
    assert anonimo.get(url).status_code == 404


def test_link_vencido_e_limite(base, mailoutbox, monkeypatch):  # noqa: F811
    u, curitiba, hoje, _f = base
    s = _os(u, curitiba, hoje, data_evento=hoje + timedelta(days=5))
    envio_email.enviar(u, s.pk, "link", para="f@x.invalid", copia="", assunto="L", texto="")
    token = _token(mailoutbox)
    monkeypatch.setattr(link_fornecedor, "LIMITE_POR_HORA", 1)
    url = reverse("fornecedor:envio", args=[token])
    anonimo = Client()
    validade = hoje + timedelta(days=90)
    anonimo.post(url, {"tipo": "certidao", "tipo_certidao": "trabalhista",
                       "arquivo": _certidao(validade)})
    r = anonimo.post(url, {"tipo": "certidao", "tipo_certidao": "trabalhista",
                           "arquivo": _certidao(validade)})
    assert r.status_code == 429
    LinkFornecedor.objects.update(expira_em=timezone.now() - timedelta(minutes=1))
    assert anonimo.get(url).status_code == 404


def test_correcoes_da_revisao_de_seguranca(base, mailoutbox, settings, monkeypatch):  # noqa: F811
    import logging

    from gestao.coffee.models import Movimento
    from gestao.coffee.pedidos import PedidoInvalido
    from gestao.plataforma import ambiente
    from gestao.plataforma.logs import MascararSegredos
    u, curitiba, hoje, _f = base
    # O link nunca conclui o pagamento, mesmo quando o próximo marco é o envio à empresa.
    s = _os(u, curitiba, hoje, data_evento=hoje - timedelta(days=10), nota_fiscal="123",
            protocolo_pagamento="12.345.678-9", atesto_em=hoje - timedelta(days=5),
            ordem_bancaria_em=hoje - timedelta(days=2))
    envio_email.enviar(u, s.pk, "link", para="f@x.invalid", copia="", assunto="L", texto="")
    s.refresh_from_db()
    assert s.envio_empresa_em is None and not s.concluida
    # Não é lista de distribuição.
    muitos = ", ".join(f"p{i}@x.invalid" for i in range(4))
    with pytest.raises(PedidoInvalido, match="Até 3 endereços"):
        envio_email.enviar(u, s.pk, "link", para=muitos, copia="", assunto="L", texto="")
    # Sem SMTP fora de lab/dev/test/preview, nada "sai" (nem o link com o token no console).
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
    monkeypatch.setattr(ambiente, "atual", lambda: "production")
    with pytest.raises(PedidoInvalido, match="não está configurado"):
        envio_email.enviar(u, s.pk, "os", para="f@x.invalid", copia="", assunto="OS", texto="")
    monkeypatch.undo()
    # O token do link não vai para o log.
    token = _token(mailoutbox)
    registro = logging.LogRecord("django.request", logging.WARNING, __file__, 1,
                                 "Unprocessable Content: %s", (f"/fornecedor/{token}/",), None)
    MascararSegredos().filter(registro)
    assert token not in registro.getMessage() and "/fornecedor/[token]/" in registro.getMessage()
    # O que o fornecedor manda não é atribuído a ninguém da equipe.
    Client().post(reverse("fornecedor:envio", args=[token]),
                  {"tipo": "certidao", "tipo_certidao": "trabalhista",
                   "arquivo": _certidao(hoje + timedelta(days=90))})
    m = Movimento.objects.get(solicitacao=s, acao="fornecedor")
    assert m.usuario is None
