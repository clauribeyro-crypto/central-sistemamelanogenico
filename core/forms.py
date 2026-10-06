from django import forms

from contas.models import Organizacao
from estoque.models import Produto

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
    produtos = forms.ModelMultipleChoiceField(
        label="Produto(s)", queryset=Produto.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Marque um só pra venda avulsa, ou mais de um quando for um kit (ex.: produto da noite + produto do dia).",
    )

    class Meta:
        model = VendaKitMentora
        fields = [
            "mentorada", "produtos", "kit_nome", "quantidade", "valor_unitario", "data_venda",
            "valor_pago", "data_pagamento_restante", "previsao_proxima_compra", "observacoes",
        ]
        widgets = {
            "kit_nome": forms.TextInput(attrs={"placeholder": "Ex.: Kit noturno + diurno"}),
            "observacoes": forms.TextInput(attrs={"placeholder": "Opcional"}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao = organizacao
        self.fields["mentorada"].queryset = Organizacao.objects.filter(ativo=True).exclude(
            pk=organizacao.pk if organizacao else None
        ).order_by("nome")
        self.fields["produtos"].queryset = Produto.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome") if organizacao else Produto.objects.none()
        self.fields["valor_pago"].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("produtos") and not cleaned.get("kit_nome"):
            raise forms.ValidationError("Marque pelo menos um produto do estoque ou dê um nome livre pro kit.")
        return cleaned
