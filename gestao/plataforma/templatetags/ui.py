"""Tags de template do Design System (carregadas como builtins).

- `{% icone "nome" %}`: ícone do sprite (decorativo por padrão);
- `{% icone "nome" rotulo="Excluir" %}`: ícone com nome acessível;
- `{{ valor|moeda }}`: R$ 1.234,56;
- `{% classe_status situacao %}`: classe CSS semântica do status.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django import template
from django.forms import BoundField, HiddenInput
from django.templatetags.static import static
from django.utils import timezone
from django.utils.html import format_html

from ..periodos import apresentar_periodo, frase_periodo, ler_data

register = template.Library()


@register.inclusion_tag("componentes/periodo_calendario.html")
def periodo_calendario(campo_inicio: BoundField | None = None,
                      campo_fim: BoundField | None = None, *, prefixo: str,
                      rotulo: str = "Período do evento", natureza: str = "evento",
                      fonte: str = "Informado no cadastro", editavel: bool = True,
                      dados: dict | None = None, inicio: object = None, fim: object = None,
                      id_folhas: str = "", id_descricao: str = "", vivo: bool = True,
                      compacto: bool = False, fim_aberto: bool = False,
                      hora: BoundField | None = None, hora_visivel: bool = True,
                      hora_rotulo: str = "Briefing") -> dict:
    """Mesma peça em todos os cadastros, preservando campos, valores e erros."""
    de = campo_inicio.value() if campo_inicio is not None else inicio
    ate = campo_fim.value() if campo_fim is not None else fim
    hoje = timezone.localdate()
    periodo = dados or apresentar_periodo(ler_data(de), ler_data(ate), hoje)
    inicio_lido, fim_lido = ler_data(de), ler_data(ate)
    if fim_aberto and inicio_lido and not ate:
        periodo = {**periodo, "aberto": True, "fim": None, "um_dia": False,
                   "dias_evento": None,
                   "frase": f"A partir de {frase_periodo(inicio_lido, inicio_lido)}"}
    texto = f"{inicio_lido:%d/%m/%Y}" if inicio_lido else ""
    if inicio_lido and fim_lido:
        texto += f" a {fim_lido:%d/%m/%Y}"

    def oculto(campo: BoundField | None, valor: object, papel: str) -> Any:
        attrs: dict[str, str | bool] = {f"data-periodo-{papel}": ""}
        if campo is not None:
            return campo.as_widget(widget=HiddenInput(), attrs=attrs)
        return HiddenInput(attrs=attrs).render(f"{prefixo}-{papel}", valor)

    # O horário (o do briefing da OS): uma coluna do próprio cartão, com o relógio do sistema.
    hora_valor = hora.value() if hora is not None else None
    hora_texto = (hora_valor.strftime("%H:%M") if hasattr(hora_valor, "strftime")
                  else (hora_valor or ""))
    return {"hora": hora, "hora_texto": hora_texto, "hora_visivel": hora_visivel,
            "hora_rotulo": hora_rotulo,
            "p": periodo, "rotulo": rotulo, "natureza": natureza, "prefixo": prefixo,
            "fonte": periodo.get("fonte") or fonte, "editavel": editavel, "hoje": hoje,
            "texto": texto, "campo_inicio": campo_inicio, "campo_fim": campo_fim,
            "inicio_oculto": oculto(campo_inicio, de, "de"),
            "fim_oculto": oculto(campo_fim, ate, "ate"), "vivo": vivo,
            "compacto": compacto, "fim_aberto": fim_aberto,
            "inicio_texto": f"{inicio_lido:%d/%m/%Y}" if inicio_lido else de or "",
            "fim_texto": f"{fim_lido:%d/%m/%Y}" if fim_lido else ate or "",
            "id_folhas": id_folhas or f"{prefixo}-periodo-folhas",
            "id_descricao": id_descricao or f"{prefixo}-periodo-resumo"}


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
    grupos: list[str] = []
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


@register.filter
def campo_acessivel(campo, tem_ajuda: object = False):
    """Renderiza o widget com aria-invalid e aria-describedby (ajuda/erro) corretos."""
    descritores = []
    if tem_ajuda:
        descritores.append(f"{campo.auto_id}-ajuda")
    if campo.errors:
        descritores.append(f"{campo.auto_id}-erro")
    attrs = {}
    if descritores:
        attrs["aria-describedby"] = " ".join(descritores)
    if campo.errors:
        attrs["aria-invalid"] = "true"
    return campo.as_widget(attrs=attrs)


@register.filter
def get_item(dicionario, chave):
    """`{{ dic|get_item:chave }}` — acesso por chave variável em templates (dict ou lista)."""
    if isinstance(dicionario, (list, tuple)):
        try:
            return dicionario[int(chave)]
        except (IndexError, TypeError, ValueError):
            return None
    try:
        return dicionario.get(chave)
    except AttributeError:
        return None


@register.simple_tag
def passo_preparacao(itens, pronto) -> int:
    """Progresso da preparação em décimos (0–10), para o índice virar barra.

    A conta inclui a revisão: as seções do domínio mais o "pronto para emitir". Sai como
    passo, não como porcentagem livre, porque a folha roda com CSP estrita — a largura vem
    de uma classe (`indice-preparacao--pN`), nunca de um `style` embutido.
    """
    secoes = list(itens or [])
    total = len(secoes) + 1
    feitas = sum(1 for item in secoes if getattr(item, "ok", None) or (
        isinstance(item, dict) and item.get("ok"))) + (1 if pronto else 0)
    return round(feitas * 10 / total) if total else 0
