from django.urls import path

from . import views

app_name = "pacientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar, name="criar"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/iniciar-protocolo/", views.iniciar_protocolo, name="iniciar_protocolo"),
]
