from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import (
    Acompanhamento,
    ConsultaPrevista,
    CustoAcompanhamento,
    Feedback,
    FaseModulacao,
    FotoEvolucao,
    KitPrevisto,
    Modulacao,
    Programa,
)


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


class ModulacaoInline(admin.TabularInline):
    model = Modulacao
    extra = 0
    show_change_link = True


@admin.register(Acompanhamento)
class AcompanhamentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("paciente", "programa", "status", "data_inicio", "data_termino_prevista", "valor_contratado")
    list_filter = ("status", "programa")
    search_fields = ("paciente__nome",)
    autocomplete_fields = ("paciente", "programa")
    date_hierarchy = "data_inicio"
    inlines = [ConsultaPrevistaInline, KitPrevistoInline, CustoAcompanhamentoInline, ModulacaoInline]


class FaseModulacaoInline(admin.TabularInline):
    model = FaseModulacao
    extra = 0


@admin.register(Modulacao)
class ModulacaoAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "numero", "concluida")
    search_fields = ("acompanhamento__paciente__nome",)
    inlines = [FaseModulacaoInline]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "data_hora", "precisou_alterar")
    list_filter = ("precisou_alterar",)
    search_fields = ("acompanhamento__paciente__nome", "relato")
    date_hierarchy = "data_hora"


@admin.register(FotoEvolucao)
class FotoEvolucaoAdmin(admin.ModelAdmin):
    list_display = ("acompanhamento", "angulo", "momento", "data")
    list_filter = ("angulo", "momento")
    search_fields = ("acompanhamento__paciente__nome",)
