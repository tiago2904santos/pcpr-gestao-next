from django.urls import path

from . import views
from . import views_pedidos as vp

app_name = "coffee"

urlpatterns = [
    path("", vp.lista, name="solicitacoes"),
    path("exportar/", vp.exportar, name="exportar"),
    path("nova/", vp.nova, name="nova"),
    path("lote-do-municipio/", vp.lote_do_municipio, name="lote_do_municipio"),
    path("solicitacoes/<int:pk>/", vp.solicitacao, name="solicitacao"),
    path("solicitacoes/<int:pk>/financeiro/", vp.salvar_financeiro, name="financeiro"),
    path("solicitacoes/<int:pk>/andamento/", vp.andamento, name="andamento"),
    path("solicitacoes/<int:pk>/conjunto/", vp.pagamento_conjunto, name="conjunto"),
    path("solicitacoes/<int:pk>/reabrir/", vp.reabrir, name="reabrir"),
    path("solicitacoes/<int:pk>/encerrar-correcao/", vp.encerrar_correcao,
         name="encerrar_correcao"),
    path("solicitacoes/<int:pk>/cancelar/", vp.cancelar, name="cancelar"),
    path("solicitacoes/<int:pk>/reativar/", vp.reativar, name="reativar"),
    path("solicitacoes/<int:pk>/excluir/", vp.excluir, name="excluir_solicitacao"),
    path("lotes/", vp.lotes, name="lotes"),
    path("cadastros/oficio/", views.configuracao, name="configuracao"),
    # Um nome por tabela (para o menu) e o genérico (para as telas).
    *(path(f"cadastros/{t}/", views.cadastros, {"tabela": t}, name=f"{t}_cadastro"
           if t == "lotes" else t) for t in views.TABELAS),
    path("cadastros/<slug:tabela>/", views.cadastros, name="cadastros"),
    path("cadastros/<slug:tabela>/salvar/", views.salvar, name="salvar"),
    path("cadastros/<slug:tabela>/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("cadastros/<slug:tabela>/<int:pk>/arquivo/", views.arquivo, name="arquivo"),
]
