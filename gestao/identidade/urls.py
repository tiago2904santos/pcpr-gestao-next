from django.urls import path

from . import views

app_name = "identidade"

urlpatterns = [
    path("entrar/", views.Entrar.as_view(), name="entrar"),
    path("sair/", views.Sair.as_view(), name="sair"),
    path("senha/", views.AlterarSenha.as_view(), name="alterar_senha"),
]
