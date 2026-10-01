"""Tags de template do Design System (carregadas como builtins).

- `{% icone "nome" %}`: ícone do sprite (decorativo por padrão);
- `{% icone "nome" rotulo="Excluir" %}`: ícone com nome acessível;
- `{{ valor|moeda }}`: R$ 1.234,56;
- `{% classe_status situacao %}`: classe CSS semântica do status.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icone(nome: str, rotulo: str = "", classe: str = "") -> str:
    href = f"{static('icons/sprite.svg')}#i-{nome}"
    css = f"icone {classe}".strip()
    if rotulo:
        return format_html(
            '<svg class="{}" role="img" aria-label="{}" focusable="false">'
            '<use href="{}"></use></svg>',
            css, rotulo, href,
        )
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>',
        css, href,
    )


def formatar_moeda(valor: Decimal | int | float | None) -> str:
    if valor is None:
        return "—"
    numero = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sinal = "-" if numero < 0 else ""
    inteiro, centavos = f"{abs(numero):.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(grupos)},{centavos}"


@register.filter
def moeda(valor: Decimal | int | float | None) -> str:
    return formatar_moeda(valor)


@register.filter
def pluralizar(n: int, formas: str) -> str:
    """`{{ n|pluralizar:"ofício,ofícios" }}` → "1 ofício" / "3 ofícios"."""
    singular, plural = formas.split(",")
    return f"{n} {singular if n == 1 else plural}"
