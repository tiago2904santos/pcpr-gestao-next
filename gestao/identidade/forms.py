from __future__ import annotations

from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils import timezone

from gestao.plataforma import ambiente

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
        "sem_demo": (
            "O usuário de demonstração ainda não existe. Rode `manage.py semear_demo`."
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
        # PREVIEW com DEMO_MODE: campos vazios entram como usuário de demonstração.
        self.entrada_demo = ambiente.demo_ativo()
        if self.entrada_demo:
            for campo in ("username", "password"):
                self.fields[campo].required = False
                self.fields[campo].widget.attrs.pop("required", None)

    def _identificador(self) -> str:
        return (self.data.get("username") or "").strip().lower()[:150]

    def clean(self):
        if (self.entrada_demo and not self.cleaned_data.get("username")
                and not self.cleaned_data.get("password")):
            return self._entrar_como_demo()
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

    def _entrar_como_demo(self):
        usuario = authenticate(self.request, demo=True)
        if usuario is None:
            raise forms.ValidationError(self.error_messages["sem_demo"], code="sem_demo")
        self.confirm_login_allowed(usuario)
        self.user_cache = usuario
        return self.cleaned_data


class FormularioTrocaSenha(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "entrada"
        # A ajuda padrão do Django é uma lista HTML (quebra o <p> do campo); uma frase basta —
        # as regras completas voltam como erro do campo quando não forem atendidas.
        self.fields["new_password1"].help_text = (
            "Ao menos 10 caracteres. Evite dados pessoais, sequências e senhas comuns.")
