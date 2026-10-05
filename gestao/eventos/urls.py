from django.urls import path

from . import views
from .catalogos import CATALOGOS

app_name = "eventos"

urlpatterns = [
    path("cadastros/", views.indice, name="cadastros"),
    *(path(f"cadastros/{slug}/", views.catalogo, {"slug": slug}, name=slug)
      for slug in CATALOGOS),
    path("cadastros/tipos-evento/<int:pk>/modelo/", views.modelo_do_tipo,
         name="modelo_do_tipo"),
]
