from django.urls import include, path

from gestao.plataforma import views as plataforma

urlpatterns = [
    path("conta/", include("gestao.identidade.urls")),
    path("viagens/", include("gestao.viagens.urls")),
    path("cadastros/", include("gestao.cadastros.urls")),
    path("imprensa/", include("gestao.imprensa.urls")),
    path("publicacoes/", include("gestao.publicacoes.urls")),
    path("palestras/", include("gestao.palestras.urls")),
    path("eventos/", include("gestao.eventos.urls")),
    path("coffee/", include("gestao.coffee.urls")),
    path("ui-lab/", include("gestao.ui_lab.urls")),
    path("saude/", plataforma.saude, name="saude"),
    path("", include("gestao.painel.urls")),
]

handler403 = "gestao.plataforma.views.erro_403"
handler404 = "gestao.plataforma.views.erro_404"
handler500 = "gestao.plataforma.views.erro_500"
