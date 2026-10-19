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
    # Link do fornecedor (sem login, por token): só a página de envio da nota e certidões.
    path("fornecedor/", include("gestao.coffee.urls_publicas")),
    path("automacao/", include("gestao.automacao.urls")),
    # Entrada da Meta (sem login, autenticada pela assinatura do corpo) — ADR 0047.
    path("integracoes/whatsapp/", include("gestao.automacao.urls_publicas")),
    # API de automação v1 (n8n e clientes de IA; credencial Bearer, sem sessão) — ADR 0020.
    path("api/automacao/v1/", include("gestao.automacao.api.urls")),
    # Links pessoais sem login (km na véspera, documentos…), por token com escopo.
    path("p/", include("gestao.automacao.urls_links")),
    path("ui-lab/", include("gestao.ui_lab.urls")),
    path("saude/", plataforma.saude, name="saude"),
    path("assistencia/", include("gestao.assistencia.urls")),
    path("ajuda/", include("gestao.assistencia.urls_ajuda")),
    path("", include("gestao.painel.urls")),
]

handler403 = "gestao.plataforma.views.erro_403"
handler404 = "gestao.plataforma.views.erro_404"
handler500 = "gestao.plataforma.views.erro_500"
