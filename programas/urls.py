from django.urls import path

from . import views

app_name = "programas"

urlpatterns = [
    path("", views.configuracoes, name="configuracoes"),
    path("tipos/novo/", views.tipo_criar, name="tipo_criar"),
    path("tipos/<int:pk>/editar/", views.tipo_editar, name="tipo_editar"),
    path("planos/novo/", views.plano_criar, name="plano_criar"),
    path("planos/<int:pk>/editar/", views.plano_editar, name="plano_editar"),
]
