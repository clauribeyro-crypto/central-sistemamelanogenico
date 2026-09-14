from django.urls import path

from . import views

app_name = "financeiro"

urlpatterns = [
    path("relatorio/", views.relatorio, name="relatorio"),
    path("pagamentos/<int:pk>/editar/", views.editar_pagamento, name="editar_pagamento"),
    path("pagamentos/<int:pk>/excluir/", views.excluir_pagamento, name="excluir_pagamento"),
]
