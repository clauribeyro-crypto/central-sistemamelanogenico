from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("semana/", views.semana, name="semana"),
    path("criar-rapido/", views.criar_consulta_rapida, name="criar_rapido"),
    path("bloquear-rapido/", views.criar_bloqueio_rapido, name="criar_bloqueio_rapido"),
    path("bloqueios/<int:pk>/excluir/", views.excluir_bloqueio, name="excluir_bloqueio"),
    path("consultas/<int:pk>/", views.detalhe_consulta, name="detalhe_consulta"),
]
