from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import Acompanhamento, ConsultaPrevista, CustoAcompanhamento, KitPrevisto, Programa


@admin.register(Programa)
class ProgramaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "duracao_meses", "valor", "valor_a_vista", "qtd_consultas", "qtd_kits", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


class ConsultaPrevistaInline(admin.TabularInline):
    model = ConsultaPrevista
    extra = 0
    autocomplete_fields = ("consulta",)


class KitPrevistoInline(admin.TabularInline):
    model = KitPrevisto
    extra = 0


class CustoAcompanhamentoInline(admin.TabularInline):
    model = CustoAcompanhamento
    extra = 0


@admin.register(Acompanhamento)
class AcompanhamentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("paciente", "programa", "status", "data_inicio", "data_termino_prevista", "valor_contratado")
    list_filter = ("status", "programa")
    search_fields = ("paciente__nome",)
    autocomplete_fields = ("paciente", "programa")
    date_hierarchy = "data_inicio"
    inlines = [ConsultaPrevistaInline, KitPrevistoInline, CustoAcompanhamentoInline]
