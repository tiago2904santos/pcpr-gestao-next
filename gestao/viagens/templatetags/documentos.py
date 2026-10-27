"""Marcação dos modelos de documento (ADR 0018): regiões, campos vinculados e quebras."""

from __future__ import annotations

from django import template
from django.utils.html import format_html, format_html_join

from ..documentos.campos import CAMPOS
from ..dominio.escrita import legivel, linhas_do_destinatario

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
    texto = "" if valor is None else str(valor).replace("\r\n", "\n").replace("\r", "\n")
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
def campo_destinos(destinos) -> str:
    """Os destinos da viagem como campo vinculado ("Cidade/UF, Cidade/UF")."""
    return format_html('<span data-campo="destinos" data-rotulo="Destinos da viagem" '
                       'data-obrigatorio>{}</span>', ", ".join(destinos or []))


@register.simple_tag
def campo_trecho(ordem: int, lado: str, momento: dict | None) -> str:
    """Saída/chegada de um trecho como campo vinculado ("dd/mm/aaaa hh:mm")."""
    momento = momento or {}
    texto = f"{momento.get('data', '')} {momento.get('hora', '')}".strip()
    rotulo = f"{'Saída' if lado == 'saida' else 'Chegada'} do trecho {ordem}"
    return format_html(
        '<span data-campo="trecho_{}_{}" data-rotulo="{}" data-obrigatorio>{}</span>',
        ordem, lado, rotulo, texto)


@register.filter(name="legivel")
def legivel_filtro(valor: object) -> str:
    """Nome, cargo ou unidade sem a caixa alta do cadastro ("AGENTE DE POLÍCIA JUDICIÁRIA" →
    "Agente de Polícia Judiciária"); as siglas conhecidas ficam."""
    return legivel(str(valor)) if valor else ""


@register.filter
def linhas_destinatario(destinatario: dict) -> list[str]:
    d = destinatario or {}
    return linhas_do_destinatario(d.get("tratamento") or "", d.get("nome") or "",
                                  d.get("cargo") or "", d.get("cidade") or "")


@register.filter
def rodape_legivel(valor: object) -> str:
    """O rodapé é "UNIDADE - Rua, nº - Bairro - Cidade/UF - CEP … - e-mail": só os trechos
    todos em maiúsculas e sem algarismos (o nome da unidade) perdem a caixa alta — o resto
    (UF, CEP, e-mail) fica como foi escrito."""
    trechos = str(valor or "").split(" - ")
    return " - ".join(legivel(t) if t.isupper() and not any(c.isdigit() for c in t) else t
                      for t in trechos)


@register.simple_tag
def ponto_de_quebra(chave: str, rotulo: str) -> str:
    return format_html('<div class="quebra" data-quebra="{}" data-rotulo="{}"></div>', chave,
                       rotulo)
