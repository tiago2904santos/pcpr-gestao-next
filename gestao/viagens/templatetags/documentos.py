"""Marcação dos modelos de documento (ADR 0018): regiões, campos vinculados e quebras."""

from __future__ import annotations

from django import template
from django.utils.html import format_html, format_html_join

from ..documentos.campos import CAMPOS

register = template.Library()

# "<br>" seguro sem mark_safe: format_html com argumento vazio.
QUEBRA_DE_LINHA = format_html("<br>{}", "")


class RegiaoNode(template.Node):
    def __init__(self, chave: str, rotulo: str, corpo):
        self.chave, self.rotulo, self.corpo = chave, rotulo, corpo

    def render(self, context):
        # O corpo já sai do motor de templates como texto seguro; chave e rótulo são escapados.
        return format_html(
            '<div class="regiao" data-regiao="{0}" data-rotulo="{1}">'
            "<!--[regiao:{0}]-->{2}<!--[/regiao:{0}]--></div>",
            self.chave, self.rotulo, self.corpo.render(context))


@register.tag
def regiao(parser, token):
    partes = token.split_contents()
    if len(partes) != 3:
        raise template.TemplateSyntaxError('{% regiao "chave" "Rótulo" %} exige chave e rótulo.')
    corpo = parser.parse(("endregiao",))
    parser.delete_first_token()
    return RegiaoNode(partes[1].strip("\"'"), partes[2].strip("\"'"), corpo)


@register.simple_tag
def campo_vinculado(chave: str, valor: object) -> str:
    """``<span data-campo>`` com o valor atual; multilinha vira ``<br>`` como no PDF."""
    campo = CAMPOS[chave]
    texto = "" if valor is None else str(valor)
    if campo.multilinha:
        conteudo = format_html_join(QUEBRA_DE_LINHA, "{}",
                                    ((linha,) for linha in texto.split("\n")))
    else:
        conteudo = format_html("{}", texto)
    formato = ('<span data-campo="{}" data-rotulo="{}"'
               + (" data-obrigatorio" if campo.obrigatorio else "")
               + (" data-multilinha" if campo.multilinha else "") + ">{}</span>")
    return format_html(formato, chave, campo.rotulo, conteudo)


@register.simple_tag
def ponto_de_quebra(chave: str, rotulo: str) -> str:
    return format_html('<div class="quebra" data-quebra="{}" data-rotulo="{}"></div>', chave,
                       rotulo)
