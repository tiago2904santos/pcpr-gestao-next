from django.urls import path

from . import views

app_name = "ajuda"

urlpatterns = [
    path("", views.central, name="central"),
    path("<slug:slug>/", views.artigo, name="artigo"),
]
