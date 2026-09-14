from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("semana/", views.semana, name="semana"),
    path("criar-rapido/", views.criar_consulta_rapida, name="criar_rapido"),
]
