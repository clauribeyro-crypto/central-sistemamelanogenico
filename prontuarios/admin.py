from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import Atendimento, Documento


@admin.register(Atendimento)
class AtendimentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
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


@admin.register(Documento)
class DocumentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "paciente", "tipo", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("nome", "paciente__nome")
    autocomplete_fields = ("paciente",)
