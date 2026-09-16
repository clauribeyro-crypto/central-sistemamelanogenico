from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("saldo-inicial/", views.salvar_saldo_inicial, name="salvar_saldo_inicial"),
    path("lancamentos/novo/", views.lancamento_criar, name="lancamento_criar"),
    path("lancamentos/<int:pk>/editar/", views.lancamento_editar, name="lancamento_editar"),
    path("lancamentos/<int:pk>/excluir/", views.lancamento_excluir, name="lancamento_excluir"),
    path("bancos/novo/", views.banco_criar, name="banco_criar"),
    path("categorias/nova/", views.categoria_criar, name="categoria_criar"),
    path("relatorio/", views.relatorio, name="relatorio"),
    path("pagamentos/<int:pk>/editar/", views.editar_pagamento, name="editar_pagamento"),
    path("pagamentos/<int:pk>/excluir/", views.excluir_pagamento, name="excluir_pagamento"),
]
