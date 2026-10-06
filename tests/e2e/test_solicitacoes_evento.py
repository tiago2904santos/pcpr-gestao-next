"""E2E: solicitação de evento social — o rascunho se grava sozinho, o envio à DG, o
despacho com texto pronto e a lista pela fila; as telas sem rolagem horizontal."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _cenario(*papeis: str):
    """Catálogos e uma solicitação completa em rascunho do operador (a carga inicial dos
    catálogos só está no banco do navegador no primeiro teste: get_or_create)."""
    from django.contrib.auth.models import Group
    from django.utils import timezone

    from gestao.cadastros.models import Municipio
    from gestao.eventos import solicitacoes
    from gestao.eventos.models import (
        Equipe,
        OrgaoResponsavel,
        Servico,
        TextoDespacho,
        TipoEvento,
    )
    from gestao.identidade.models import Usuario

    u = Usuario.objects.get(login="operador")
    for p in papeis:
        u.groups.add(Group.objects.get(name=p))
    hoje = timezone.localdate()
    cidade = Municipio.objects.get_or_create(codigo_ibge="4106902",
                                             defaults={"nome": "Curitiba", "uf": "PR"})[0]
    TextoDespacho.objects.create(nome="Deferido (e2e)", texto="Deferido. Providencie-se.")
    dados = {"data_solicitacao": hoje, "data_inicio_evento": hoje + timedelta(days=20),
             "data_fim_evento": hoje + timedelta(days=20), "municipio": cidade,
             "tipo_evento": TipoEvento.objects.get_or_create(nome="Feira")[0],
             "solicitante_nome": "Escola com um nome bem comprido para a quebra (e2e)",
             "solicitante_cargo_unidade": "Direção",
             "orgao_responsavel": OrgaoResponsavel.objects.get_or_create(nome="Delegacia-Geral")[0],
             "local_evento": "Ginásio (e2e)", "tipo_operacao": "diaria"}
    estrutura = solicitacoes.Estrutura(
        servicos={Servico.objects.get_or_create(nome="Emissão de CIN")[0].pk: ""},
        equipes={Equipe.objects.get_or_create(nome="Alfa")[0].pk: 3})
    return u, solicitacoes.criar(u, dados, estrutura)


def test_rascunho_envio_e_despacho(logado, dados_e2e):
    from gestao.eventos.models import Solicitacao

    _u, s = _cenario("GESTOR_DG")
    pg = logado
    pg.goto(f"/eventos/solicitacoes/{s.pk}/")
    pg.locator("#id_contato").fill("(41) 3333-4444")
    expect(pg.locator("[data-status-salvamento]")).to_contain_text(re.compile("Salvo"),
                                                                    timeout=10000)
    s.refresh_from_db()
    assert s.contato == "(41) 3333-4444"

    pg.get_by_role("button", name=re.compile("^Enviar")).first.click()
    expect(pg.locator(".selo", has_text="Aguardando despacho").first).to_be_visible()

    pg.locator("label.opcao", has=pg.get_by_text("Atender", exact=True)).click()
    pg.get_by_role("combobox", name="Textos prontos").click()
    pg.get_by_role("option", name="Deferido (e2e)").click()
    expect(pg.locator("#observacao-dg")).to_have_value("Deferido. Providencie-se.")
    pg.get_by_role("button", name="Registrar decisão").click()
    expect(pg.locator(".selo", has_text="Deferida").first).to_be_visible()
    s.refresh_from_db()
    assert s.status == Solicitacao.Status.DEFERIDA
    assert s.observacoes_dg == "Deferido. Providencie-se."

    pg.goto("/eventos/solicitacoes/?fila=deferidas")
    expect(pg.locator(".registro__link", has_text="Feira · Curitiba")).to_be_visible()
    assert not pg.erros_console  # type: ignore[attr-defined]


@pytest.mark.parametrize("largura", [360, 1440])
def test_telas_sem_rolagem_horizontal(logado, dados_e2e, largura):
    _u, s = _cenario("GESTOR_DG")
    pg = logado
    pg.set_viewport_size({"width": largura, "height": 900})
    for rota in ("/eventos/solicitacoes/", "/eventos/solicitacoes/nova/",
                 f"/eventos/solicitacoes/{s.pk}/", "/eventos/solicitacoes/?fila=despacho"):
        pg.goto(rota)
        excesso = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert excesso <= 0, f"{rota} @ {largura}px: rolagem horizontal de {excesso}px"
