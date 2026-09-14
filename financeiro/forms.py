from django import forms

from .models import Pagamento


class PagamentoForm(forms.ModelForm):
    # Obrigatório no formulário (mesmo sendo opcional no modelo) — os
    # relatórios do Financeiro filtram por essa data, então deixar em
    # branco faria o lançamento sumir silenciosamente dos períodos.
    # format="%Y-%m-%d" é essencial: sem ele, o widget usa o formato
    # localizado (dd/mm/aaaa em pt-br) no atributo value, que o
    # <input type="date"> do navegador rejeita silenciosamente.
    data_vencimento = forms.DateField(
        label="Vencimento", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Pagamento
        fields = ["valor", "status", "forma_pagamento", "data_vencimento", "data_pagamento", "observacoes"]
        widgets = {
            "data_pagamento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == Pagamento.Status.PAGO and not cleaned.get("forma_pagamento"):
            self.add_error("forma_pagamento", "Informe a forma de pagamento para marcar como pago.")
        return cleaned

    def save(self, commit=True):
        pagamento = super().save(commit=False)
        if pagamento.status == Pagamento.Status.PAGO and not pagamento.data_pagamento:
            from django.utils import timezone
            pagamento.data_pagamento = timezone.localdate()
        if commit:
            pagamento.save()
        return pagamento
