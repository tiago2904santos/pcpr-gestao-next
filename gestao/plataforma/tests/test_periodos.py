from datetime import date

import pytest
from django import forms
from django.template.loader import render_to_string

from gestao.plataforma.periodos import apresentar_periodo, ler_data
from gestao.plataforma.templatetags.ui import periodo_calendario


@pytest.mark.parametrize(("valor", "esperado"), [
    ("2026-10-27", date(2026, 10, 27)),
    ("27/10/2026", date(2026, 10, 27)),
    ("29/02/2024", date(2024, 2, 29)),
    ("29/02/2026", None), ("31/04/2026", None), ("", None), (None, None),
])
def test_data_de_formulario(valor, esperado):
    assert ler_data(valor) == esperado


def test_duracao_e_antecedencia_sao_contagens_distintas():
    p = apresentar_periodo(date(2026, 10, 27), date(2026, 11, 3), date(2026, 10, 14))
    assert p["dias_evento"] == 8
    assert p["antecedencia"] == 13
    assert p["frase"] == "27 de outubro a 3 de novembro de 2026"


def test_um_dia_e_periodo_invertido():
    hoje = date(2026, 10, 14)
    um = apresentar_periodo(hoje, None, hoje)
    assert um["um_dia"] and um["dias_evento"] == 1 and um["antecedencia"] == 0
    invertido = apresentar_periodo(hoje, date(2026, 10, 13), hoje)
    assert invertido["dias_evento"] is None and invertido["frase"] == "Confira a data final"


def test_virada_de_ano_na_frase():
    p = apresentar_periodo(date(2026, 12, 31), date(2027, 1, 2), date(2026, 12, 30))
    assert p["dias_evento"] == 3 and p["antecedencia"] == 1
    assert p["frase"] == "31 de dezembro de 2026 a 2 de janeiro de 2027"


class FormularioPeriodo(forms.Form):
    inicio = forms.DateField(required=False)
    fim = forms.DateField(required=False)


def test_campos_prefixados_e_erro_nao_sao_descartados():
    form = FormularioPeriodo(data={"evento-inicio": "data inválida", "evento-fim": ""},
                             prefix="evento")
    assert not form.is_valid()
    contexto = periodo_calendario(form["inicio"], form["fim"], prefixo="teste")
    html = render_to_string("componentes/periodo_calendario.html", contexto)
    assert 'name="evento-inicio"' in html and 'id="id_evento-inicio"' in html
    assert 'value="data inválida"' in html and 'aria-invalid="true"' in html
    assert 'id="teste-periodo-erros"' in html
    assert "<noscript>" in html


def test_consulta_e_zero_de_antecedencia_preservados():
    contexto = periodo_calendario(prefixo="consulta", editavel=False,
                                  dados=apresentar_periodo(date(2026, 10, 14), None,
                                                         date(2026, 10, 14)))
    html = render_to_string("componentes/periodo_calendario.html", contexto)
    assert "<strong>0</strong>" in html and "começa hoje" in html
    assert "readonly" in html and " disabled" in html


def test_substituicao_compacta_com_fim_aberto():
    form = FormularioPeriodo(initial={"inicio": date(2026, 10, 14)})
    contexto = periodo_calendario(form["inicio"], form["fim"], prefixo="substituicao",
                                  compacto=True, fim_aberto=True, natureza="substituição")
    html = render_to_string("componentes/periodo_calendario.html", contexto)
    assert "A partir de 14 de outubro de 2026" in html
    assert "até encerrar" in html and "∞" in html
    assert 'name="fim"' in html and contexto["p"]["fim"] is None
    assert "mesa-evento__antecedencia" not in html


def test_substituicao_com_fim_informado():
    contexto = periodo_calendario(prefixo="substituicao", inicio=date(2026, 10, 14),
                                  fim=date(2026, 10, 21), compacto=True, fim_aberto=True,
                                  natureza="substituição")
    html = render_to_string("componentes/periodo_calendario.html", contexto)
    assert "8 dias de substituição" in html
    assert "até encerrar" not in html
