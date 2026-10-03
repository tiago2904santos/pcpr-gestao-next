from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    path("servidores/", views.servidores, name="servidores"),
    path("viaturas/", views.viaturas, name="viaturas"),
    path("diarias/", views.diarias, name="diarias"),
    path("api/municipios/", views.buscar_municipios, name="buscar_municipios"),
    path("textos-prontos/", views.textos_prontos, name="textos"),
    path("textos-prontos/salvar/", views.salvar_texto, name="salvar_texto"),
    path("textos-prontos/<int:pk>/padrao/", views.texto_padrao, name="texto_padrao"),
    path("textos-prontos/<int:pk>/ativo/", views.texto_ativo, name="texto_ativo"),
    path("textos-prontos/<int:pk>/excluir/", views.texto_excluir, name="texto_excluir"),
]
