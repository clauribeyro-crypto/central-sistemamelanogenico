from django.contrib import admin

from contas.admin import OrganizacaoAdminMixin

from .models import Banco, CategoriaFinanceira, Lancamento, Pagamento, Recebimento, Servico


@admin.register(Servico)
class ServicoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "valor_padrao", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


class RecebimentoInline(admin.TabularInline):
    model = Recebimento
    extra = 0
    fields = ("valor", "forma_pagamento", "data", "observacoes")


@admin.register(Pagamento)
class PagamentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "paciente", "valor", "total_recebido", "saldo_pendente", "status", "data_vencimento",
    )
    list_filter = ("status",)
    search_fields = ("paciente__nome",)
    autocomplete_fields = ("paciente", "consulta", "servico", "acompanhamento")
    date_hierarchy = "data_vencimento"
    readonly_fields = ("status", "forma_pagamento", "data_pagamento")
    inlines = [RecebimentoInline]

    def save_formset(self, request, form, formset, change):
        # Recebimento herda ModeloDaOrganizacao — precisa da organização
        # preenchida, que aqui vem do próprio Pagamento pai.
        instancias = formset.save(commit=False)
        for instancia in instancias:
            if isinstance(instancia, Recebimento) and not instancia.organizacao_id:
                instancia.organizacao = form.instance.organizacao
            instancia.save()
        formset.save_m2m()


@admin.register(Banco)
class BancoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("nome", "grupo", "ativo")
    list_filter = ("grupo", "ativo")
    search_fields = ("nome",)


@admin.register(Lancamento)
class LancamentoAdmin(OrganizacaoAdminMixin, admin.ModelAdmin):
    list_display = ("descricao", "categoria", "banco", "valor", "status", "data")
    list_filter = ("status", "categoria__grupo", "banco")
    search_fields = ("descricao",)
    autocomplete_fields = ("categoria", "banco")
    date_hierarchy = "data"
