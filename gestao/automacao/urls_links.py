from django.urls import path, re_path

from . import views_links

app_name = "link_acesso"

urlpatterns = [
    path("<str:token>/", views_links.abrir, name="abrir"),
    re_path(r"^(?P<token>[A-Za-z0-9_-]{32,128})/(?P<resto>[a-z0-9-]{1,40})/$", views_links.abrir,
            name="abrir_acao"),
]
