"""Autenticação por login ou e-mail institucional (sem distinção de caixa) e, só no
PREVIEW com DEMO_MODE, entrada sem senha do usuário de demonstração."""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from gestao.plataforma import ambiente

from .models import Usuario

# Usuário de demonstração criado por `semear_demo` (dados 100% fictícios).
LOGIN_DEMO = "demo"


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        identificador = username.strip()
        usuario = Usuario.objects.filter(
            Q(login__iexact=identificador) | Q(email__iexact=identificador)
        ).first()
        if usuario is None:
            Usuario().set_password(password)  # tempo constante contra enumeração
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None


class DemoBackend(ModelBackend):
    """Autentica o usuário de demonstração sem senha — **somente** com `demo=True`, no
    PREVIEW e com DEMO_MODE (`ambiente.demo_ativo()`); em qualquer outro caso, recusa.
    Só entra em AUTHENTICATION_BACKENDS em `config.settings.preview`."""

    def authenticate(self, request, username=None, password=None, demo: bool = False,
                     **kwargs):
        if not demo or not ambiente.demo_ativo():
            return None
        usuario = Usuario.objects.filter(login=LOGIN_DEMO).first()
        if usuario is None or not self.user_can_authenticate(usuario):
            return None
        return usuario
