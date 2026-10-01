from django.urls import path

from . import views

app_name = "viagens"

urlpatterns = [
    path("", views.painel, name="painel"),
]
