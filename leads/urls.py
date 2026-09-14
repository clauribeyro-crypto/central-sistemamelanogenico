from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("", views.kanban, name="kanban"),
    path("novo/", views.criar_lead, name="criar_lead"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/mover/", views.mover_etapa, name="mover_etapa"),
    path("<int:pk>/responder-rapido/", views.marcar_respondido_rapido, name="marcar_respondido_rapido"),
    path("<int:pk>/ligacao/", views.registrar_ligacao, name="registrar_ligacao"),
    path("<int:pk>/whatsapp/", views.enviar_whatsapp, name="enviar_whatsapp"),
    path("<int:pk>/resultado/", views.resultado_contato, name="resultado_contato"),
    path("<int:pk>/pausar/", views.pausar, name="pausar"),
    path("<int:pk>/retomar/", views.retomar, name="retomar"),
    path("<int:pk>/perder/", views.perder, name="perder"),
    path("<int:pk>/agendar/", views.agendar, name="agendar"),
]
