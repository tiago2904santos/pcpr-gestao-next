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
    path("solicitacoes/<int:pk>/protocolo/", vp.protocolo_pagamento, name="protocolo"),
    path("solicitacoes/<int:pk>/protocolo/baixar/", vp.baixar_protocolo,
         name="baixar_protocolo"),
    path("solicitacoes/<int:pk>/pdf/<slug:qual>/", vp.baixar_pdf, name="baixar_pdf"),
    path("solicitacoes/<int:pk>/pdf/<slug:qual>/anexar/", vp.anexar_pdf, name="anexar_pdf"),
    path("solicitacoes/<int:pk>/pdf/<slug:qual>/remover/", vp.remover_pdf, name="remover_pdf"),
    path("solicitacoes/<int:pk>/documentos/<slug:tipo>/", vp.documento, name="documento"),
    path("solicitacoes/<int:pk>/documentos/<slug:tipo>/assinado/", vp.anexar_assinada,
         name="anexar_assinada"),
    path("solicitacoes/<int:pk>/documentos/<slug:tipo>/assinado/remover/", vp.remover_assinada,
         name="remover_assinada"),
    path("solicitacoes/<int:pk>/reabrir/", vp.reabrir, name="reabrir"),
    path("solicitacoes/<int:pk>/encerrar-correcao/", vp.encerrar_correcao,
         name="encerrar_correcao"),
    path("solicitacoes/<int:pk>/cancelar/", vp.cancelar, name="cancelar"),
    path("solicitacoes/<int:pk>/reativar/", vp.reativar, name="reativar"),
    path("solicitacoes/<int:pk>/excluir/", vp.excluir, name="excluir_solicitacao"),
    path("lotes/", vp.lotes, name="lotes"),
    path("certidoes/", vp.certidoes, name="certidoes"),
    path("certidoes/anexar/", vp.anexar_certidao, name="anexar_certidao"),
    path("certidoes/<int:pk>/arquivo/", vp.arquivo_certidao, name="arquivo_certidao"),
    path("cadastros/oficio/", views.configuracao, name="configuracao"),
    # Um nome por tabela (para o menu) e o genérico (para as telas).
    *(path(f"cadastros/{t}/", views.cadastros, {"tabela": t}, name=f"{t}_cadastro"
           if t == "lotes" else t) for t in views.TABELAS),
    path("cadastros/<slug:tabela>/", views.cadastros, name="cadastros"),
    path("cadastros/<slug:tabela>/salvar/", views.salvar, name="salvar"),
    path("cadastros/<slug:tabela>/<int:pk>/excluir/", views.excluir, name="excluir"),
    path("cadastros/<slug:tabela>/<int:pk>/arquivo/", views.arquivo, name="arquivo"),
]
