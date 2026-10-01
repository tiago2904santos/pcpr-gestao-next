from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator

from .forms import FormularioEntrada, FormularioTrocaSenha
from .models import TentativaAcesso, Usuario


@method_decorator(login_not_required, name="dispatch")
class Entrar(auth_views.LoginView):
    template_name = "identidade/entrar.html"
    authentication_form = FormularioEntrada
    redirect_authenticated_user = True

    def form_valid(self, form):
        TentativaAcesso.objects.filter(identificador=form._identificador()).delete()
        return super().form_valid(form)


class Sair(auth_views.LogoutView):
    http_method_names = ["post", "options"]


class AlterarSenha(auth_views.PasswordChangeView):
    template_name = "identidade/alterar_senha.html"
    form_class = FormularioTrocaSenha
    success_url = reverse_lazy("painel:inicio")

    def form_valid(self, form):
        resposta = super().form_valid(form)
        usuario = self.request.user
        if not isinstance(usuario, Usuario):
            raise PermissionDenied
        Usuario.objects.filter(pk=usuario.pk).update(deve_trocar_senha=False)
        messages.success(self.request, "Senha alterada com sucesso.")
        return resposta
