from django.contrib import admin

from .models import Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "telefone", "email", "cpf", "ativo", "criado_em")
    list_filter = ("ativo", "sexo")
    search_fields = ("nome", "cpf", "telefone", "email")
    ordering = ("nome",)
    fieldsets = (
        ("Dados pessoais", {
            "fields": ("nome", "cpf", "data_nascimento", "sexo", "ativo"),
        }),
        ("Contato", {
            "fields": ("telefone", "email", "endereco"),
        }),
        ("Histórico", {
            "fields": ("historico_saude", "observacoes"),
        }),
    )
