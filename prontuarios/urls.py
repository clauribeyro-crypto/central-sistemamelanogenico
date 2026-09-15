from django.urls import path

from . import views

app_name = "prontuarios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/<int:paciente_pk>/", views.criar, name="criar"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("pacientes/<int:paciente_pk>/anamnese/", views.anamnese, name="anamnese"),
    path("pacientes/<int:paciente_pk>/documentos/novo/", views.documento_criar, name="documento_criar"),
    path("documentos/<int:pk>/excluir/", views.documento_excluir, name="documento_excluir"),
]
