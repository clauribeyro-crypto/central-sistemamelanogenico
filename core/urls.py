from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("indicadores/", views.indicadores, name="indicadores"),
    path("em-breve/<str:modulo>/", views.em_breve, name="em_breve"),
]
