from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("", views.kanban, name="kanban"),
    path("novo/", views.criar_lead, name="criar_lead"),
    path("origens/nova/", views.origem_criar, name="origem_criar"),
    path("importacao/", views.configuracao_importacao, name="configuracao_importacao"),
    path("social-selling/", views.registrar_social_selling, name="registrar_social_selling"),
    path("marketing/", views.painel_marketing, name="painel_marketing"),
    path("duplicados/", views.duplicados, name="duplicados"),
    path("duplicados/mesclar/", views.mesclar_duplicados, name="mesclar_duplicados"),
    path("webhook/<str:token>/", views.webhook_importar_lead, name="webhook_importar_lead"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar_lead, name="editar_lead"),
    path("<int:pk>/mover/", views.mover_etapa, name="mover_etapa"),
    path("<int:pk>/responder-rapido/", views.marcar_respondido_rapido, name="marcar_respondido_rapido"),
    path("<int:pk>/mover-agendados/", views.mover_para_agendados, name="mover_para_agendados"),
    path("<int:pk>/ligacao/", views.registrar_ligacao, name="registrar_ligacao"),
    path("<int:pk>/whatsapp/", views.enviar_whatsapp, name="enviar_whatsapp"),
    path("<int:pk>/resultado/", views.resultado_contato, name="resultado_contato"),
    path("<int:pk>/pausar/", views.pausar, name="pausar"),
    path("<int:pk>/retomar/", views.retomar, name="retomar"),
    path("<int:pk>/perder/", views.perder, name="perder"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/agendar/", views.agendar, name="agendar"),
]
