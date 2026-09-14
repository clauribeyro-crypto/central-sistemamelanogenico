from django import forms

from pacientes.models import Paciente
from profissionais.models import Profissional

from .models import TipoConsulta


class ConsultaRapidaForm(forms.Form):
    """Formulário do modal de criação rápida, clicando num horário vazio da agenda."""

    paciente = forms.ModelChoiceField(queryset=Paciente.objects.none())
    profissional = forms.ModelChoiceField(queryset=Profissional.objects.none())
    tipo_consulta = forms.ModelChoiceField(queryset=TipoConsulta.objects.none())
    data = forms.DateField()
    hora = forms.TimeField()
    duracao_minutos = forms.IntegerField(min_value=5, initial=30)
    observacoes = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["profissional"].queryset = Profissional.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["tipo_consulta"].queryset = TipoConsulta.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("ordem", "nome")
