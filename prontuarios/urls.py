from django.urls import path

from . import views

app_name = "prontuarios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/<int:paciente_pk>/", views.criar, name="criar"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("pacientes/<int:paciente_pk>/anamnese/", views.anamnese, name="anamnese"),
    path(
        "pacientes/<int:paciente_pk>/anamnese/imprimir/",
        views.anamnese_imprimir, name="anamnese_imprimir",
    ),
    path(
        "pacientes/<int:paciente_pk>/anamnese/gerar-link/",
        views.link_anamnese_criar, name="link_anamnese_criar",
    ),
    path("anamnese/links/<int:pk>/desativar/", views.link_anamnese_desativar, name="link_anamnese_desativar"),
    path("anamnese/publica/<uuid:token>/", views.anamnese_publica, name="anamnese_publica"),
    path(
        "pacientes/<int:paciente_pk>/checkin/gerar-link/",
        views.link_checkin_criar, name="link_checkin_criar",
    ),
    path("pacientes/<int:paciente_pk>/checkin/novo/", views.checkin_criar, name="checkin_criar"),
    path("checkin/<int:pk>/excluir/", views.checkin_excluir, name="checkin_excluir"),
    path("checkin/publico/<uuid:token>/", views.checkin_publico, name="checkin_publico"),
    path("pacientes/<int:paciente_pk>/documentos/novo/", views.documento_criar, name="documento_criar"),
    path("documentos/<int:pk>/excluir/", views.documento_excluir, name="documento_excluir"),
]
