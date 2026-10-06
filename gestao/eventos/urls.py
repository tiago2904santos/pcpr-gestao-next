from django.urls import path

from . import views, views_painel
from . import views_solicitacoes as vs
from .catalogos import CATALOGOS

app_name = "eventos"

urlpatterns = [
    path("", views_painel.painel_eventos, name="painel"),
    path("solicitacoes/", vs.lista, name="solicitacoes"),
    path("solicitacoes/exportar/", vs.exportar, name="exportar"),
    path("solicitacoes/nova/", vs.nova, name="nova"),
    path("solicitacoes/<int:pk>/", vs.solicitacao, name="solicitacao"),
    path("solicitacoes/<int:pk>/autosave/", vs.autosave, name="autosave"),
    path("solicitacoes/<int:pk>/enviar/", vs.enviar, name="enviar"),
    path("solicitacoes/<int:pk>/despachar/", vs.despachar, name="despachar"),
    path("solicitacoes/<int:pk>/concluir/", vs.concluir, name="concluir"),
    path("solicitacoes/<int:pk>/cancelar/", vs.cancelar, name="cancelar"),
    path("solicitacoes/<int:pk>/transferir/", vs.transferir, name="transferir"),
    path("solicitacoes/<int:pk>/duplicar/", vs.duplicar, name="duplicar"),
    path("solicitacoes/<int:pk>/excluir/", vs.excluir, name="excluir"),
    path("solicitacoes/<int:pk>/viagem/", vs.gerar_viagem, name="gerar_viagem"),
    path("solicitacoes/<int:pk>/anexos/", vs.anexar, name="anexar"),
    path("solicitacoes/<int:pk>/anexos/<int:anexo_pk>/", vs.abrir_anexo, name="abrir_anexo"),
    path("solicitacoes/<int:pk>/anexos/<int:anexo_pk>/remover/", vs.remover_anexo,
         name="remover_anexo"),
    path("cadastros/", views.indice, name="cadastros"),
    *(path(f"cadastros/{slug}/", views.catalogo, {"slug": slug}, name=slug)
      for slug in CATALOGOS),
    path("cadastros/tipos-evento/<int:pk>/modelo/", views.modelo_do_tipo,
         name="modelo_do_tipo"),
]
