from decimal import Decimal

from django import forms

from .models import Banco, CategoriaFinanceira, Lancamento, Pagamento, Recebimento


class PagamentoForm(forms.ModelForm):
    # format="%Y-%m-%d" é essencial: sem ele, o widget usa o formato
    # localizado (dd/mm/aaaa em pt-br) no atributo value, que o
    # <input type="date"> do navegador rejeita silenciosamente.
    data_vencimento = forms.DateField(
        label="Vencimento", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Pagamento
        # status, forma_pagamento e data_pagamento não entram aqui — são
        # calculados automaticamente a partir dos recebimentos (ver
        # Pagamento.recalcular_status).
        fields = ["valor", "data_vencimento", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }


class RecebimentoForm(forms.ModelForm):
    data = forms.DateField(
        label="Data", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Recebimento
        fields = ["valor", "forma_pagamento", "data", "observacoes"]
        widgets = {
            "observacoes": forms.TextInput(attrs={"placeholder": "Opcional — ex.: entrada, sinal, restante"}),
        }

    def __init__(self, *args, pagamento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pagamento = pagamento
        if pagamento is not None:
            self.fields["valor"].initial = pagamento.saldo_pendente

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor <= 0:
            raise forms.ValidationError("O valor precisa ser maior que zero.")
        if self.pagamento is not None and valor > self.pagamento.saldo_pendente:
            raise forms.ValidationError(
                f"Esse valor é maior que o saldo pendente (R$ {self.pagamento.saldo_pendente:.2f})."
            )
        return valor


class BancoForm(forms.ModelForm):
    class Meta:
        model = Banco
        fields = ["nome", "ativo"]


class CategoriaFinanceiraForm(forms.ModelForm):
    class Meta:
        model = CategoriaFinanceira
        fields = ["nome", "grupo", "ativo"]


class LancamentoForm(forms.ModelForm):
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    class Meta:
        model = Lancamento
        fields = ["data", "descricao", "categoria", "banco", "valor", "status", "observacoes"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaFinanceira.objects.filter(
            organizacao=organizacao, ativo=True
        )
        self.fields["banco"].queryset = Banco.objects.filter(organizacao=organizacao, ativo=True)
        self.fields["banco"].required = False
