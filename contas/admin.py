from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organizacao, Usuario


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Organização", {"fields": ("organizacao",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Organização", {"fields": ("organizacao",)}),
    )
    list_display = ("username", "email", "organizacao", "is_staff", "is_superuser")
    list_filter = UserAdmin.list_filter + ("organizacao",)

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
