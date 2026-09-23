from django.urls import path

from . import views

app_name = "pacientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar, name="criar"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/mesclar/", views.mesclar_selecionar, name="mesclar_selecionar"),
    path("<int:pk>/mesclar/<int:duplicada_pk>/", views.mesclar_confirmar, name="mesclar_confirmar"),
    path("<int:pk>/iniciar-protocolo/", views.iniciar_protocolo, name="iniciar_protocolo"),
    path("<int:pk>/descartar-fechamento/", views.descartar_fechamento, name="descartar_fechamento"),
    path("<int:pk>/reabrir-fechamento/", views.reabrir_fechamento, name="reabrir_fechamento"),
    path("crm/fechamento/", views.crm_fechamento, name="crm_fechamento"),
]
