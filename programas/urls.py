from django.urls import path

from . import views

app_name = "programas"

urlpatterns = [
    path("", views.configuracoes, name="configuracoes"),
    path("tipos/novo/", views.tipo_criar, name="tipo_criar"),
    path("tipos/<int:pk>/editar/", views.tipo_editar, name="tipo_editar"),
    path("planos/novo/", views.plano_criar, name="plano_criar"),
    path("planos/<int:pk>/editar/", views.plano_editar, name="plano_editar"),
    path(
        "acompanhamentos/<int:pk>/status/",
        views.mudar_status_acompanhamento,
        name="mudar_status_acompanhamento",
    ),
    path("acompanhamentos/<int:pk>/editar/", views.acompanhamento_editar, name="acompanhamento_editar"),
    path("fases/<int:pk>/", views.fase_detalhe, name="fase_detalhe"),
    path("acompanhamentos/<int:acompanhamento_pk>/feedbacks/novo/", views.feedback_criar, name="feedback_criar"),
    path("feedbacks/<int:pk>/editar/", views.feedback_editar, name="feedback_editar"),
    path("acompanhamentos/<int:acompanhamento_pk>/fotos/nova/", views.foto_criar, name="foto_criar"),
    path("fotos/<int:pk>/excluir/", views.foto_excluir, name="foto_excluir"),
    path("kits/<int:pk>/montar/", views.kit_montar, name="kit_montar"),
    path("kits/<int:pk>/nao-se-aplica/", views.kit_nao_se_aplica, name="kit_nao_se_aplica"),
    path(
        "consultas-previstas/<int:pk>/vincular/",
        views.vincular_consulta_prevista,
        name="vincular_consulta_prevista",
    ),
]
