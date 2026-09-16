from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import Produto, ProducaoPendente, Recompra


@admin.register(Produto)
class ProdutoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "estoque_atual", "estoque_minimo", "duracao_estimada_dias", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(ProducaoPendente)
class ProducaoPendenteAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("produto", "quantidade", "status", "previsao_conclusao")
    list_filter = ("status",)


@admin.register(Recompra)
class RecompraAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("paciente", "produto", "data_prevista", "data_realizada")
    list_filter = ("data_realizada",)
    search_fields = ("paciente__nome", "produto__nome")
