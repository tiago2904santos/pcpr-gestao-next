"""Autenticação por login ou e-mail institucional (sem distinção de caixa)."""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import Usuario


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
