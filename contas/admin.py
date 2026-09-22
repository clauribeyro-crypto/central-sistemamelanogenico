from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organizacao, Usuario


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = (
        "nome", "slug", "ativo",
        "modulo_leads_ativo", "modulo_financeiro_ativo", "modulo_programas_ativo",
        "criado_em",
    )
    list_filter = ("ativo",)
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    fieldsets = (
        (None, {"fields": ("nome", "slug", "ativo")}),
        ("Agenda", {"fields": ("agenda_hora_inicio", "agenda_hora_fim", "agenda_intervalo_minutos")}),
        ("Leads", {"fields": ("dias_lead_parado",)}),
        ("Financeiro", {"fields": ("saldo_inicial_financeiro",)}),
        ("Módulos ativos", {
            "fields": ("modulo_leads_ativo", "modulo_financeiro_ativo", "modulo_programas_ativo"),
            "description": "Desmarque um módulo pra escondê-lo do menu e bloquear o acesso pra essa organização.",
        }),
    )


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Organização", {"fields": ("organizacao", "papel")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Organização", {"fields": ("organizacao", "papel")}),
    )
    list_display = ("username", "email", "organizacao", "papel", "is_staff", "is_superuser")
    list_filter = UserAdmin.list_filter + ("organizacao", "papel")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organizacao=request.user.organizacao)


class OrganizacaoAdminMixin:
    """
    Mixin para ModelAdmin de qualquer modelo que herda de ModeloDaOrganizacao:
    - restringe a listagem à organização do usuário logado;
    - preenche a organização automaticamente ao criar um registro;
    - restringe as opções de campos de FK (paciente, profissional, etc.) à
      mesma organização;
    - esconde o campo "organização" do formulário para quem não é admin geral.

    Um superusuário (admin geral) continua vendo e podendo escolher qualquer
    organização normalmente.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organizacao=request.user.organizacao)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.organizacao_id:
            obj.organizacao = request.user.organizacao
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if not request.user.is_superuser and hasattr(field, "queryset"):
            if hasattr(field.queryset.model, "organizacao_id"):
                field.queryset = field.queryset.filter(
                    organizacao=request.user.organizacao
                )
        return field

    def get_exclude(self, request, obj=None):
        exclude = super().get_exclude(request, obj) or ()
        if not request.user.is_superuser:
            return (*exclude, "organizacao")
        return exclude
