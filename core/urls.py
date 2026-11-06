from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("indicadores/", views.indicadores, name="indicadores"),
    path("mentoradas/", views.painel_mentoradas, name="painel_mentoradas"),
    path("mentoradas/vendas-kit/", views.vendas_kit_mentoradas, name="vendas_kit_mentoradas"),
    path("mentoradas/vendas-kit/<int:pk>/editar/", views.vendas_kit_mentora_editar, name="vendas_kit_mentora_editar"),
    path("mentoradas/vendas-kit/<int:pk>/excluir/", views.vendas_kit_mentora_excluir, name="vendas_kit_mentora_excluir"),
    path("mentoradas/mentoria/", views.pagamentos_mentoria, name="pagamentos_mentoria"),
    path("mentoradas/mentoria/<int:pk>/editar/", views.pagamentos_mentoria_parcela_editar, name="pagamentos_mentoria_parcela_editar"),
    path("mentoradas/mentoria/<int:pk>/excluir/", views.pagamentos_mentoria_parcela_excluir, name="pagamentos_mentoria_parcela_excluir"),
    path("em-breve/<str:modulo>/", views.em_breve, name="em_breve"),
]
