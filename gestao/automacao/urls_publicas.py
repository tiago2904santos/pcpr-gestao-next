from django.urls import path

from . import views_webhook

app_name = "integracoes_whatsapp"

urlpatterns = [
    path("webhook/", views_webhook.whatsapp, name="webhook"),
]
