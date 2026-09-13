from django.contrib import admin

from .models import Consulta


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = (
        "data_hora", "paciente", "profissional", "duracao_minutos", "status",
    )
    list_filter = ("status", "profissional")
    search_fields = ("paciente__nome", "profissional__nome", "motivo")
    date_hierarchy = "data_hora"
    autocomplete_fields = ("paciente", "profissional")
    ordering = ("data_hora",)
