from django.contrib import admin

from .models import Atendimento


@admin.register(Atendimento)
class AtendimentoAdmin(admin.ModelAdmin):
    list_display = ("data_hora", "paciente", "profissional")
    list_filter = ("profissional",)
    search_fields = ("paciente__nome", "diagnostico", "queixa_principal")
    date_hierarchy = "data_hora"
    autocomplete_fields = ("paciente", "profissional", "consulta")
    fieldsets = (
        (None, {
            "fields": ("paciente", "profissional", "consulta", "data_hora"),
        }),
        ("Prontuário", {
            "fields": (
                "queixa_principal", "historico_atual", "exame_fisico",
                "diagnostico", "conduta", "prescricao", "observacoes",
            ),
        }),
    )
