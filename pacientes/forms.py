from django import forms

from programas.models import Programa


class IniciarProtocoloForm(forms.Form):
    programa = forms.ModelChoiceField(queryset=Programa.objects.none(), label="Programa")
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    valor_contratado = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text="Deixe em branco para usar o valor padrão do programa.",
    )
    desconto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    forma_pagamento = forms.CharField(max_length=100, required=False)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programa"].queryset = Programa.objects.filter(organizacao=organizacao, ativo=True)
