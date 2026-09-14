from django.urls import path

from . import views

app_name = "prontuarios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/<int:paciente_pk>/", views.criar, name="criar"),
    path("<int:pk>/editar/", views.editar, name="editar"),
]
