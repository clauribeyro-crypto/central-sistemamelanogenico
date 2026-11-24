from django.contrib import admin

from .models import ContratoMentoria, ParcelaMentoria, VendaKitMentora


@admin.register(VendaKitMentora)
class VendaKitMentoraAdmin(admin.ModelAdmin):
    list_display = ("mentorada", "kit_nome", "quantidade", "valor_unitario", "data_venda", "valor_pago")
    list_filter = ("mentorada",)
    search_fields = ("kit_nome", "mentorada__nome")


@admin.register(ContratoMentoria)
class ContratoMentoriaAdmin(admin.ModelAdmin):
    list_display = ("mentorada", "valor_total", "total_pago", "saldo_pendente", "data_inicio")
    search_fields = ("mentorada__nome",)


@admin.register(ParcelaMentoria)
class ParcelaMentoriaAdmin(admin.ModelAdmin):
    list_display = ("contrato", "valor", "data_prevista", "data_pagamento")
    list_filter = ("contrato__mentorada",)
