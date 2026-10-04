from django.urls import path

from . import views, views_crud, views_usuarios

app_name = "cadastros"

urlpatterns = [
    path("", views_crud.indice, name="indice"),
    path("usuarios/", views_usuarios.usuarios, name="usuarios"),
    path("usuarios/salvar/", views_usuarios.salvar_usuario, name="salvar_usuario"),
    path("usuarios/<int:pk>/ativo/", views_usuarios.alternar_ativo_usuario,
         name="alternar_ativo_usuario"),
    path("servidores/", views_crud.servidores, name="servidores"),
    path("servidores/salvar/", views_crud.salvar_servidor, name="salvar_servidor"),
    path("viaturas/", views_crud.viaturas, name="viaturas"),
    path("viaturas/salvar/", views_crud.salvar_viatura, name="salvar_viatura"),
    path("diarias/", views_crud.diarias, name="diarias"),
    path("diarias/salvar/", views_crud.salvar_vigencia, name="salvar_vigencia"),
    path("diarias/<int:pk>/excluir/", views_crud.excluir_vigencia, name="excluir_vigencia"),
    path("configuracao/", views_crud.configuracao, name="configuracao"),
    path("configuracao/substituicoes/salvar/", views_crud.salvar_substituicao,
         name="salvar_substituicao"),
    path("configuracao/substituicoes/<int:pk>/ativo/", views_crud.alternar_substituicao,
         name="alternar_substituicao"),
    path("api/municipios/", views.buscar_municipios, name="buscar_municipios"),
    path("api/servidores/", views_crud.buscar_servidores, name="buscar_servidores"),
    path("textos-prontos/", views.textos_prontos, name="textos"),
    path("textos-prontos/salvar/", views.salvar_texto, name="salvar_texto"),
    path("textos-prontos/<int:pk>/padrao/", views.texto_padrao, name="texto_padrao"),
    path("textos-prontos/<int:pk>/ativo/", views.texto_ativo, name="texto_ativo"),
    path("textos-prontos/<int:pk>/excluir/", views.texto_excluir, name="texto_excluir"),
    # Cadastros simples (unidades, cargos, combustíveis) e as ações comuns a todos.
    path("unidades/", views_crud.catalogo, {"slug": "unidades"}, name="unidades"),
    path("cargos/", views_crud.catalogo, {"slug": "cargos"}, name="cargos"),
    path("combustiveis/", views_crud.catalogo, {"slug": "combustiveis"}, name="combustiveis"),
    # Catálogos do plano de trabalho.
    path("programas/", views_crud.catalogo, {"slug": "programas"}, name="programas"),
    path("horarios/", views_crud.catalogo, {"slug": "horarios"}, name="horarios"),
    path("atividades/", views_crud.catalogo, {"slug": "atividades"}, name="atividades"),
    path("conjuntos/", views_crud.catalogo, {"slug": "conjuntos"}, name="conjuntos"),
    path("<slug:slug>/salvar/", views_crud.salvar_catalogo, name="salvar_catalogo"),
    path("<slug:slug>/<int:pk>/ativo/", views_crud.alternar_ativo, name="alternar_ativo"),
    path("<slug:slug>/<int:pk>/padrao/", views_crud.definir_padrao, name="definir_padrao"),
    path("<slug:slug>/<int:pk>/excluir/", views_crud.excluir, name="excluir"),
]
