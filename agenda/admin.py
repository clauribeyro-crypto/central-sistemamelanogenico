from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render

from contas.admin import OrganizacaoAdminMixin

from .models import Consulta, HorarioBloqueado, TipoConsulta


class ReatribuirTipoConsultaForm(forms.Form):
    novo_tipo = forms.ModelChoiceField(
        queryset=TipoConsulta.objects.none(), label="Novo tipo de consulta",
        help_text="Todas as consultas selecionadas passam a ter esse tipo.",
    )

    def __init__(self, *args, organizacoes_permitidas=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = TipoConsulta.objects.order_by("organizacao__nome", "ordem", "nome")
        if organizacoes_permitidas is not None:
            qs = qs.filter(organizacao__in=organizacoes_permitidas)
        self.fields["novo_tipo"].queryset = qs


class TipoConsultaAdminForm(forms.ModelForm):
    class Meta:
        model = TipoConsulta
        fields = "__all__"
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}


@admin.register(TipoConsulta)
class TipoConsultaAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    form = TipoConsultaAdminForm
    list_display = ("nome", "cor", "duracao_padrao_minutos", "valor", "ordem", "ativo")
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
        "duracao_minutos", "valor", "status",
    )
    list_filter = ("status", "profissional", "tipo_consulta")
    search_fields = ("paciente__nome", "profissional__nome", "motivo")
    date_hierarchy = "data_hora"
    autocomplete_fields = ("paciente", "profissional", "lead", "reagendada_de")
    ordering = ("data_hora",)
    actions = ["reatribuir_tipo_consulta"]

    @admin.action(description="Reatribuir tipo das consultas selecionadas")
    def reatribuir_tipo_consulta(self, request, queryset):
        """
        Corrige em massa consultas marcadas com o tipo errado (ex.: a SDR
        sempre agenda como "Consulta inicial" quando na verdade é "Consulta
        de diagnóstico") — sem isso, a única forma de corrigir seria editar
        consulta por consulta. Só troca o tipo; valor já lançado e o
        lançamento financeiro vinculado (se houver) não são mexidos (ver
        Consulta.save/sincronizar_receita_prevista) — se o novo tipo tiver
        conta_para_fechamento diferente do antigo, isso muda quais relatórios
        (fila de fechamento, indicadores, painel de marketing) passam a
        contar essas consultas a partir de agora.
        """
        organizacoes_permitidas = None
        if not request.user.is_superuser:
            organizacoes_permitidas = [request.user.organizacao_id]

        if "aplicar" in request.POST:
            form = ReatribuirTipoConsultaForm(request.POST, organizacoes_permitidas=organizacoes_permitidas)
            if form.is_valid():
                novo_tipo = form.cleaned_data["novo_tipo"]
                total = queryset.update(tipo_consulta=novo_tipo)
                self.message_user(
                    request,
                    f'{total} consulta{"s" if total != 1 else ""} reatribuída{"s" if total != 1 else ""} '
                    f'pro tipo "{novo_tipo}".',
                    level=messages.SUCCESS,
                )
                return None
        else:
            form = ReatribuirTipoConsultaForm(organizacoes_permitidas=organizacoes_permitidas)

        return render(
            request, "admin/agenda/reatribuir_tipo_consulta.html",
            {
                "form": form,
                "consultas": queryset,
                "titulo": "Reatribuir tipo de consulta",
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action_name": "reatribuir_tipo_consulta",
                "opts": self.model._meta,
            },
        )
