from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render

from contas.admin import OrganizacaoAdminMixin

from .models import (
    HistoricoLead, Lead, MensagemModelo, MotivoPerda, Origem, PausaLead,
    ProvaSocial, WebhookImportacao,
)


class ReatribuirOrigemForm(forms.Form):
    nova_origem = forms.ModelChoiceField(
        queryset=Origem.objects.none(), label="Nova origem",
        help_text="Todas as leads selecionadas passam a ter essa origem.",
    )

    def __init__(self, *args, organizacoes_permitidas=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Origem.objects.order_by("organizacao__nome", "nome")
        if organizacoes_permitidas is not None:
            qs = qs.filter(organizacao__in=organizacoes_permitidas)
        self.fields["nova_origem"].queryset = qs


@admin.register(Origem)
class OrigemAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    # "organizacao" aparece pra administradora geral conseguir diferenciar
    # nomes repetidos entre clínicas (ex.: "Instagram" de cada mentorada) —
    # pra quem não é superusuária, o próprio mixin já filtra só a própria
    # organização, então a coluna não teria repetição mesmo sem isso.
    list_display = ("nome", "organizacao", "ativo", "para_mentoria", "padrao_campanha")
    list_filter = ("organizacao", "para_mentoria")
    list_editable = ("ativo", "para_mentoria")
    search_fields = ("nome",)


@admin.register(MotivoPerda)
class MotivoPerdaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "organizacao", "ativo")
    list_filter = ("organizacao",)
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
    actions = ["reatribuir_origem"]

    @admin.action(description="Reatribuir origem das leads selecionadas")
    def reatribuir_origem(self, request, queryset):
        """
        Corrige em massa leads que entraram com a origem errada (ex.: um
        formulário externo mandando sempre a mesma origem fixa, não
        importa de qual aba/formulário realmente veio — ver
        leads.views.webhook_importar_lead) — sem isso, a única forma de
        corrigir seria editar lead por lead.
        """
        organizacoes_permitidas = None
        if not request.user.is_superuser:
            organizacoes_permitidas = [request.user.organizacao_id]

        if "aplicar" in request.POST:
            form = ReatribuirOrigemForm(request.POST, organizacoes_permitidas=organizacoes_permitidas)
            if form.is_valid():
                nova_origem = form.cleaned_data["nova_origem"]
                total = queryset.update(origem=nova_origem)
                self.message_user(
                    request,
                    f'{total} lead{"s" if total != 1 else ""} reatribuída{"s" if total != 1 else ""} '
                    f'pra origem "{nova_origem}".',
                    level=messages.SUCCESS,
                )
                return None
        else:
            form = ReatribuirOrigemForm(organizacoes_permitidas=organizacoes_permitidas)

        return render(
            request, "admin/leads/reatribuir_origem.html",
            {
                "form": form,
                "leads": queryset,
                "titulo": "Reatribuir origem",
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action_name": "reatribuir_origem",
                "opts": self.model._meta,
            },
        )


@admin.register(WebhookImportacao)
class WebhookImportacaoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("organizacao", "origem_padrao", "ativo", "total_recebidos", "total_duplicados", "ultimo_recebido_em")
    readonly_fields = ("token", "total_recebidos", "total_duplicados", "ultimo_recebido_em", "criado_em")
    autocomplete_fields = ("origem_padrao",)
