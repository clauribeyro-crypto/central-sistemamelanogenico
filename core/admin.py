from django.contrib import admin

from .models import VendaKitMentora


@admin.register(VendaKitMentora)
class VendaKitMentoraAdmin(admin.ModelAdmin):
    list_display = ("mentorada", "kit_nome", "quantidade", "valor_unitario", "data_venda", "valor_pago")
    list_filter = ("mentorada",)
    search_fields = ("kit_nome", "mentorada__nome")
