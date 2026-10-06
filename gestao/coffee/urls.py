from django.urls import path

from . import views

app_name = "coffee"

urlpatterns = [
    path("cadastros/oficio/", views.configuracao, name="configuracao"),
    # Um nome por tabela (para o menu) e o genérico (para as telas).
    *(path(f"cadastros/{t}/", views.cadastros, {"tabela": t}, name=t) for t in views.TABELAS),
    path("cadastros/<slug:tabela>/", views.cadastros, name="cadastros"),
    path("cadastros/<slug:tabela>/salvar/", views.salvar, name="salvar"),
    path("cadastros/<slug:tabela>/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("cadastros/<slug:tabela>/<int:pk>/arquivo/", views.arquivo, name="arquivo"),
]
