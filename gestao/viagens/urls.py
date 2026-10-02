from django.urls import path

from . import views, views_roteiros

app_name = "viagens"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("oficios/", views.lista, name="oficios"),
    path("oficios/novo/", views.novo, name="novo"),
    path("oficios/<int:pk>/", views.detalhe, name="detalhe"),
    path("oficios/<int:pk>/editar/", views.editar, name="editar"),
    path("oficios/<int:pk>/resumo/", views.resumo, name="resumo"),
    path("oficios/<int:pk>/equipe/adicionar/", views.adicionar_viajante,
         name="adicionar_viajante"),
    path("oficios/<int:pk>/equipe/<int:viajante_id>/remover/", views.remover_viajante,
         name="remover_viajante"),
    path("oficios/<int:pk>/equipe/motorista/", views.definir_motorista,
         name="definir_motorista"),
    path("oficios/<int:pk>/diarias/", views.secao_diarias, name="secao_diarias"),
    path("oficios/<int:pk>/emitir/", views.revisar_emissao, name="revisar_emissao"),
    path("oficios/<int:pk>/emitir/confirmar/", views.emitir, name="emitir"),
    path("oficios/<int:pk>/reabrir/", views.reabrir, name="reabrir"),
    path("oficios/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("oficios/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("oficios/<int:pk>/documentos/", views.documentos_parcial, name="documentos"),
    path("oficios/<int:pk>/minuta.pdf", views.previa, name="previa"),
    path("documentos/<int:documento_id>/", views.baixar_documento, name="baixar_documento"),
    path("api/servidores/", views.buscar_servidores, name="buscar_servidores"),
    path("api/rota/", views.rota, name="rota"),
    path("roteiros/", views_roteiros.lista, name="roteiros"),
    path("roteiros/novo/", views_roteiros.novo, name="novo_roteiro"),
    path("roteiros/previa-diarias/", views_roteiros.previa_diarias,
         name="previa_diarias_roteiro"),
    path("roteiros/previa-trechos/", views_roteiros.previa_trechos,
         name="previa_trechos_roteiro"),
    path("roteiros/autosave/", views_roteiros.autosave, name="autosave_roteiro"),
    path("roteiros/<int:pk>/editar/", views_roteiros.editar, name="editar_roteiro"),
    path("roteiros/<int:pk>/cancelar/", views_roteiros.cancelar, name="cancelar_roteiro"),
    path("roteiros/<int:pk>/reativar/", views_roteiros.reativar, name="reativar_roteiro"),
    path("roteiros/<int:pk>/excluir/", views_roteiros.excluir, name="excluir_roteiro"),
    path("roteiros/<int:pk>/criar-oficio/", views_roteiros.criar_oficio,
         name="criar_oficio_do_roteiro"),
]
