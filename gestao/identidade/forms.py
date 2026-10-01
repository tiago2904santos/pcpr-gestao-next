from __future__ import annotations

from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils import timezone

from .models import TentativaAcesso


class FormularioEntrada(AuthenticationForm):
    """Login com bloqueio progressivo por identificador (login/e-mail)."""

    error_messages = {
        "invalid_login": "Usuário ou senha incorretos. Confira e tente novamente.",
        "inactive": "Este acesso está desativado. Procure o administrador da unidade.",
        "bloqueado": (
            "Muitas tentativas sem sucesso. Por segurança, aguarde 15 minutos ou procure o "
            "administrador da unidade."
        ),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Usuário ou e-mail institucional"
        self.fields["username"].widget.attrs.update(
            {"class": "entrada", "autocomplete": "username", "autofocus": True,
             "placeholder": "usuario ou nome@pc.pr.gov.br", "autocapitalize": "none",
             "spellcheck": "false"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "entrada", "autocomplete": "current-password"}
        )

    def _identificador(self) -> str:
        return (self.data.get("username") or "").strip().lower()[:150]

    def clean(self):
        identificador = self._identificador()
        janela = timezone.now() - timedelta(seconds=settings.LOGIN_JANELA_SEGUNDOS)
        recentes = TentativaAcesso.objects.filter(
            identificador=identificador, ocorrida_em__gte=janela
        ).count()
        if identificador and recentes >= settings.LOGIN_MAX_TENTATIVAS:
            raise forms.ValidationError(self.error_messages["bloqueado"], code="bloqueado")
        try:
            return super().clean()
        except forms.ValidationError:
            if identificador:
                ip = self.request.META.get("REMOTE_ADDR") if self.request else None
                TentativaAcesso.objects.create(identificador=identificador, ip=ip)
            raise


class FormularioTrocaSenha(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "entrada"
