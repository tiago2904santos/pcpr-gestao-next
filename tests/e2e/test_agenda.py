"""E2E: agenda — a viagem aparece no mês, o filtro tira a fonte, a lista mostra os detalhes
e o compromisso leva à folha da viagem."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_agenda_mes_filtro_e_lista(logado, dados_e2e):
    from django.utils import timezone

    from gestao.identidade.models import Usuario
    from gestao.viagens import viagem
    from gestao.viagens.models import Viagem

    hoje = timezone.localdate()
    v = viagem.criar(Usuario.objects.get(login="operador"))
    Viagem.objects.filter(pk=v.pk).update(data_inicio=hoje, titulo="Feira",
                                          motivo="Apoio à feira (e2e)")
    pg = logado
    pg.goto("/agenda/")
    item = pg.get_by_role("link", name="Apoio à feira (e2e)").first
    expect(item).to_be_visible()
    pg.get_by_label("Viagens", exact=True).uncheck()
    pg.get_by_role("button", name="Aplicar").click()
    expect(pg.get_by_role("link", name="Apoio à feira (e2e)")).to_have_count(0)
    pg.get_by_label("Viagens", exact=True).check()
    pg.get_by_role("button", name="Aplicar").click()
    pg.get_by_role("link", name="Lista").click()
    expect(pg.locator(".agenda-lista")).to_contain_text("Motivo: Apoio à feira (e2e)")
    pg.get_by_role("link", name="Semana", exact=True).click()
    expect(pg.locator(".agenda-semana")).to_contain_text("Apoio à feira (e2e)")
    pg.get_by_role("link", name="Próxima semana").click()
    pg.get_by_role("link", name="Semana anterior").click()
    pg.get_by_role("link", name="Dia", exact=True).click()
    expect(pg.locator(".agenda-lista")).to_contain_text("Motivo: Apoio à feira (e2e)")
    pg.get_by_role("link", name="Apoio à feira (e2e)").first.click()
    expect(pg).to_have_url(re.compile(rf"/viagens/viagens/{v.pk}/$"))
    # No mês, o compromisso abre o dossiê (A2c), que leva ao registro.
    pg.goto("/agenda/")
    pg.locator(".agenda-item", has_text="Apoio à feira (e2e)").first.click()
    expect(pg.locator("#dossie")).to_be_visible()
    pg.get_by_role("link", name="Abrir no sistema").click()
    expect(pg).to_have_url(re.compile(rf"/viagens/viagens/{v.pk}/$"))
