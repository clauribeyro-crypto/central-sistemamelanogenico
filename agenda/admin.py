from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import Consulta, HorarioBloqueado, TipoConsulta


@admin.register(TipoConsulta)
class TipoConsultaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "cor", "duracao_padrao_minutos", "ordem", "ativo")
    list_editable = ("ordem", "ativo")
    ordering = ("ordem", "nome")


@admin.register(HorarioBloqueado)
class HorarioBloqueadoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("profissional", "motivo", "inicio", "fim")
    list_filter = ("motivo", "profissional")
    autocomplete_fields = ("profissional",)
    date_hierarchy = "inicio"


@admin.register(Consulta)
class ConsultaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "data_hora", "paciente", "profissional", "tipo_consulta",
        "duracao_minutos", "status",
    )
    list_filter = ("status", "profissional", "tipo_consulta")
    search_fields = ("paciente__nome", "profissional__nome", "motivo")
    date_hierarchy = "data_hora"
    autocomplete_fields = ("paciente", "profissional", "lead", "reagendada_de")
    ordering = ("data_hora",)
