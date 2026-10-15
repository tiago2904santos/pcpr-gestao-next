"""Apresentação pura de períodos, compartilhada pelos cadastros."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")


def ler_data(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str):
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    return None


def antecedencia_do_inicio(inicio: date | None, hoje: date) -> tuple[int | None, str]:
    """Contagem para a tela; não avalia prazo institucional."""
    if inicio is None:
        return None, "defina o período"
    dias = (inicio - hoje).days
    if dias == 0:
        return 0, "começa hoje"
    quantidade = abs(dias)
    unidade = "dia" if quantidade == 1 else "dias"
    rotulo = "de antecedência" if dias > 0 else "desde o início"
    return quantidade, f"{unidade} {rotulo}"


def frase_periodo(inicio: date, fim: date) -> str:
    if fim == inicio:
        return f"{inicio.day} de {MESES[inicio.month - 1]} de {inicio.year}"
    if (inicio.month, inicio.year) == (fim.month, fim.year):
        return f"{inicio.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
    if inicio.year == fim.year:
        return (f"{inicio.day} de {MESES[inicio.month - 1]} a {fim.day} de "
                f"{MESES[fim.month - 1]} de {fim.year}")
    return (f"{inicio.day} de {MESES[inicio.month - 1]} de {inicio.year} a "
            f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}")


def apresentar_periodo(inicio: date | None, fim: date | None, hoje: date) -> dict[str, Any]:
    antecedencia, rotulo = antecedencia_do_inicio(inicio, hoje)
    dados: dict[str, Any] = {"inicio": inicio, "fim": fim,
                             "antecedencia": antecedencia, "rotulo_antecedencia": rotulo}
    if inicio is None:
        return dados
    fim = fim or inicio
    valido = fim >= inicio
    return {**dados, "fim": fim, "um_dia": inicio == fim,
            "dias_evento": (fim - inicio).days + 1 if valido else None,
            "frase": frase_periodo(inicio, fim) if valido else "Confira a data final"}
