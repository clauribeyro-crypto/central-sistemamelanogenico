from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import (
    HistoricoLead, Lead, MensagemModelo, MotivoPerda, Origem, PausaLead,
    ProvaSocial, WebhookImportacao,
)


@admin.register(Origem)
class OrigemAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "ativo")
    list_editable = ("ativo",)
    search_fields = ("nome",)


@admin.register(MotivoPerda)
class MotivoPerdaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "ativo")
    list_editable = ("ativo",)
    search_fields = ("nome",)


@admin.register(MensagemModelo)
class MensagemModeloAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("etapa", "ativo")
    list_filter = ("etapa", "ativo")


@admin.register(ProvaSocial)
class ProvaSocialAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome_interno", "autorizacao_uso_imagem", "ativo")
    list_filter = ("ativo", "autorizacao_uso_imagem")
    search_fields = ("nome_interno",)


class HistoricoLeadInline(admin.TabularInline):
    model = HistoricoLead
    extra = 0
    readonly_fields = ("data_hora", "tipo", "descricao", "responsavel")
    can_delete = False
    ordering = ("-data_hora",)

    def has_add_permission(self, request, obj=None):
        return False


class PausaLeadInline(admin.TabularInline):
    model = PausaLead
    extra = 0
    fields = ("criada_em", "motivo", "data_retomada_prevista", "observacao", "responsavel", "retomado_em")
    readonly_fields = ("criada_em",)


@admin.register(Lead)
class LeadAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "nome", "whatsapp", "origem", "status", "etapa", "responsavel",
        "entrou_em", "proxima_acao_em",
    )
    list_filter = ("status", "etapa", "origem", "responsavel")
    search_fields = ("nome", "whatsapp", "telefone")
    autocomplete_fields = ("origem", "perdido_motivo", "paciente")
    date_hierarchy = "entrou_em"
    inlines = [PausaLeadInline, HistoricoLeadInline]


@admin.register(WebhookImportacao)
class WebhookImportacaoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("organizacao", "origem_padrao", "ativo", "total_recebidos", "total_duplicados", "ultimo_recebido_em")
    readonly_fields = ("token", "total_recebidos", "total_duplicados", "ultimo_recebido_em", "criado_em")
    autocomplete_fields = ("origem_padrao",)
