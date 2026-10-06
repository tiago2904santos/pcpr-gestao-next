from django.urls import path

from . import escala, pauta, views, views_agenda, views_notificacoes, views_relatorios

app_name = "painel"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("notificacoes/", views_notificacoes.central, name="notificacoes"),
    path("notificacoes/marcar-lidas/", views_notificacoes.marcar_lidas,
         name="marcar_notificacoes_lidas"),
    path("notificacoes/<int:pk>/abrir/", views_notificacoes.abrir, name="abrir_notificacao"),
    path("busca/", views.busca, name="busca"),
    path("agenda/", views_agenda.agenda_view, name="agenda"),
    path("agenda/pauta/", pauta.baixar, name="pauta"),
    path("agenda/escala/", escala.escala, name="escala"),
    path("agenda/assinatura/", views_agenda.assinar, name="assinar_agenda"),
    path("agenda/ics/<str:token>.ics", views_agenda.feed_ics, name="feed_ics"),
    path("relatorios/", views_relatorios.relatorios, name="relatorios"),
    path("relatorios/planilha/", views_relatorios.exportar_relatorio,
         name="exportar_relatorio"),
]
