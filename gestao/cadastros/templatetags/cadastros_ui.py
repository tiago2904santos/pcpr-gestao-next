"""Decisões de Cadastros usadas pelo shell, sem dependência reversa da plataforma."""

from django import template

from gestao.cadastros import policies

register = template.Library()


@register.simple_tag
def pode_ver_dados_unidade(usuario) -> bool:
    return bool(usuario and usuario.is_authenticated and policies.pode_ver_configuracao(usuario))
