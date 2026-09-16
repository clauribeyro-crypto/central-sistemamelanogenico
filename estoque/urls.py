from django.urls import path

from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("produtos/novo/", views.produto_criar, name="produto_criar"),
    path("produtos/<int:pk>/editar/", views.produto_editar, name="produto_editar"),
    path("produtos/<int:pk>/entrada/", views.entrada_estoque, name="entrada_estoque"),
    path("producao/novo/", views.producao_criar, name="producao_criar"),
    path("producao/<int:pk>/pronto/", views.producao_marcar_pronto, name="producao_marcar_pronto"),
    path("recompras/novo/", views.recompra_criar, name="recompra_criar"),
    path("recompras/<int:pk>/comprou/", views.recompra_marcar_comprada, name="recompra_marcar_comprada"),
]
