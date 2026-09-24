from django import forms

from financeiro.models import Pagamento
from programas.models import Programa

from .models import Paciente


class PacienteRapidoForm(forms.ModelForm):
    """Cadastro rápido — só o essencial pra já abrir a ficha e seguir o atendimento."""

    class Meta:
        model = Paciente
        fields = ["nome", "telefone", "cidade"]


class IniciarProtocoloForm(forms.Form):
    programa = forms.ModelChoiceField(queryset=Programa.objects.none(), label="Programa")
    data_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    valor_contratado = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text="Deixe em branco para usar o valor padrão do programa.",
    )
    desconto = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    forma_pagamento = forms.CharField(max_length=100, required=False)
    valor_recebido_agora = forms.DecimalField(
        label="Valor já recebido", max_digits=10, decimal_places=2, required=False, min_value=0,
        help_text=(
            "Deixe em branco se ainda não recebeu nada — dá pra registrar depois, no Financeiro. "
            "Preencha pra já lançar o pagamento (parcial ou total) na hora, útil pra cadastrar uma "
            "paciente antiga que já pagou tudo ou parte do tratamento."
        ),
    )
    forma_recebimento = forms.ChoiceField(
        label="Forma do valor já recebido",
        choices=[("", "---------")] + list(Pagamento.FormaPagamento.choices), required=False,
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programa"].queryset = Programa.objects.filter(organizacao=organizacao, ativo=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("valor_recebido_agora") and not cleaned.get("forma_recebimento"):
            self.add_error("forma_recebimento", "Informe a forma do valor já recebido.")
        return cleaned
