"""Termo com mais de uma viatura e a data do evento.

- Ofícios vinculados trazem cada um a sua viatura, com a equipe dele; o termo emite um
  documento por viatura e o de cada servidor sai com a viatura em que ele vai.
- A data do termo é a do evento (plano de trabalho → OS → viagem, só com início e fim); sem
  nenhum, o período da viagem.
- A tela: calendário de mesa (sem campo de texto) e "Quem vai em cada viatura" com um
  seletor por servidor (`viatura_do_<id>`). Dados fictícios.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from gestao.cadastros.models import Viatura
from gestao.viagens import termos, viagem
from gestao.viagens.models import Oficio, TermoAutorizacao

from .cenarios import cenario_completo

pytestmark = pytest.mark.django_db
VIATURA = Oficio.TipoTransporte.VIATURA


@pytest.fixture
def c():
    return cenario_completo()


def _cliente(usuario) -> Client:
    cli = Client()
    cli.force_login(usuario)
    return cli


def _dois_com_viaturas(c):
    """Dois ofícios da mesma viagem, cada um na sua viatura."""
    op = c.usuarios["operador"]
    o1 = Oficio.objects.get(pk=c.ids["oficio_emitido"])
    o2 = Oficio.objects.get(pk=c.ids["oficio_rascunho"])
    v1, v2 = Viatura.objects.all()[:2]
    Oficio.objects.filter(pk=o1.pk).update(viatura=v1, tipo_transporte=VIATURA)
    Oficio.objects.filter(pk=o2.pk).update(viatura=v2, tipo_transporte=VIATURA)
    v = viagem.criar(op)
    Oficio.objects.filter(pk__in=[o1.pk, o2.pk]).update(viagem=v)
    o1.refresh_from_db()
    o2.refresh_from_db()
    return op, o1, o2, v1, v2, v


class TestViaturas:
    def test_cada_oficio_traz_a_sua_viatura_com_a_equipe(self, c):
        op, o1, o2, v1, v2, _ = _dois_com_viaturas(c)
        termo = termos.salvar(op, oficios=[o1, o2])
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        assert [g.viatura for g in ef.viaturas] == [v1, v2]
        do_1 = {v.servidor for v in o1.viajantes.all()}
        so_do_2 = {v.servidor for v in o2.viajantes.all()} - do_1  # quem está nos dois fica na 1.ª
        assert do_1 and so_do_2
        assert all(ef.viatura_de(s) == v1 for s in do_1)
        assert all(ef.viatura_de(s) == v2 for s in so_do_2)
        # Um termo por viatura, cada um com a sua chave.
        chaves = [d["chave"] for d in termos.documentos_do_termo(termo)]
        assert termos.chave_da_viatura(0, v1) in chaves
        assert termos.chave_da_viatura(1, v2) in chaves

    def test_uma_viatura_so_leva_todos(self, c):
        op = c.usuarios["operador"]
        oficio = Oficio.objects.get(pk=c.ids["oficio_emitido"])
        v1 = Viatura.objects.first()
        Oficio.objects.filter(pk=oficio.pk).update(viatura=v1, tipo_transporte=VIATURA)
        termo = termos.salvar(op, oficio=Oficio.objects.get(pk=oficio.pk))
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        assert ef.servidores and all(ef.viatura_de(s) == v1 for s in ef.servidores)


class TestDataDoEvento:
    def test_a_data_da_viagem_vence_a_ida_e_volta(self, c):
        op, o1, o2, _, _, v = _dois_com_viaturas(c)
        type(v).objects.filter(pk=v.pk).update(data_inicio=date(2030, 3, 10),
                                               data_fim=date(2030, 3, 11))
        oficios = [Oficio.objects.get(pk=o1.pk), Oficio.objects.get(pk=o2.pk)]
        termo = termos.salvar(op, oficios=oficios)
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        assert (ef.inicio, ef.fim) == (date(2030, 3, 10), date(2030, 3, 11))
        assert ef.fonte_periodo.startswith("Período do evento — Viagem")

    def test_data_pela_metade_nao_conta(self, c):
        op, o1, o2, _, _, v = _dois_com_viaturas(c)
        type(v).objects.filter(pk=v.pk).update(data_inicio=date(2030, 3, 10), data_fim=None)
        oficios = [Oficio.objects.get(pk=o1.pk), Oficio.objects.get(pk=o2.pk)]
        assert termos.periodo_do_evento(oficios) == (None, None, "")
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termos.salvar(op, oficios=oficios).pk))
        assert ef.fonte_periodo.startswith("Período da viagem")


class TestTela:
    def test_calendario_sem_campo_e_seletor_por_servidor(self, c):
        op, o1, o2, _, _, _ = _dois_com_viaturas(c)
        termo = termos.salvar(op, oficios=[o1, o2])
        html = _cliente(op).get(reverse("viagens:editar_termo", args=[termo.pk])).content.decode()
        assert 'class="mesa-evento' in html and 'type="hidden" id="termo-periodo"' in html
        assert "Alterar a data</label>" not in html
        assert "Quem vai em cada viatura" in html and "data-escala" in html
        servidor = termos.efetivo(termo).servidores[0]
        assert f'name="viatura_do_{servidor.pk}"' in html

    def test_trocar_de_viatura_pela_tela(self, c):
        op, o1, o2, v1, v2, _ = _dois_com_viaturas(c)
        termo = termos.salvar(op, oficios=[o1, o2])
        ef = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        servidor = next(s for s in ef.servidores if ef.viatura_de(s) == v1)
        marcas = {f"viatura_do_{s.pk}": (ef.viatura_de(s).pk if ef.viatura_de(s) else "")
                  for s in ef.servidores}
        marcas[f"viatura_do_{servidor.pk}"] = v2.pk
        r = _cliente(op).post(reverse("viagens:autosave_termo", args=[termo.pk]), {
            "oficios": [o1.pk, o2.pk], "viaturas": [v1.pk, v2.pk], **marcas})
        assert r.json()["salvo"] is True
        depois = termos.efetivo(TermoAutorizacao.objects.get(pk=termo.pk))
        assert depois.viatura_de(servidor) == v2
