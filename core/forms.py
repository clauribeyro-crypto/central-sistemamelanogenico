from django import forms

from contas.models import Organizacao

from .models import VendaKitMentora


class VendaKitMentoraForm(forms.ModelForm):
    data_venda = forms.DateField(
        label="Data da venda", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    data_pagamento_restante = forms.DateField(
        label="Pagamento do saldo previsto pra", required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    previsao_proxima_compra = forms.DateField(
        label="Previsão de próxima compra", required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = VendaKitMentora
        fields = [
            "mentorada", "kit_nome", "quantidade", "valor_unitario", "data_venda",
            "valor_pago", "data_pagamento_restante", "previsao_proxima_compra", "observacoes",
        ]
        widgets = {
            "kit_nome": forms.TextInput(attrs={"placeholder": "Ex.: Kit noturno + diurno"}),
            "observacoes": forms.TextInput(attrs={"placeholder": "Opcional"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mentorada"].queryset = Organizacao.objects.filter(ativo=True).order_by("nome")
        self.fields["valor_pago"].required = False
