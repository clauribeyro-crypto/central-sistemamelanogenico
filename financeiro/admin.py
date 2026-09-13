from django.contrib import admin

from .models import Pagamento, Servico


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "valor_padrao", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = (
        "paciente", "valor", "forma_pagamento", "status",
        "data_vencimento", "data_pagamento",
    )
    list_filter = ("status", "forma_pagamento")
    search_fields = ("paciente__nome",)
    autocomplete_fields = ("paciente", "consulta", "servico")
    date_hierarchy = "data_vencimento"
