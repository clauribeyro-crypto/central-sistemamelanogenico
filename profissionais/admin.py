from django.contrib import admin

from .models import HorarioAtendimento, Profissional


class HorarioAtendimentoInline(admin.TabularInline):
    model = HorarioAtendimento
    extra = 1


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ("nome", "especialidade", "telefone", "email", "ativo")
    list_filter = ("ativo", "especialidade")
    search_fields = ("nome", "especialidade")
    inlines = [HorarioAtendimentoInline]
