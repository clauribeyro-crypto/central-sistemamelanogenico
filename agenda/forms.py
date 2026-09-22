from django import forms

from pacientes.models import Paciente
from profissionais.models import Profissional

from .models import Consulta, HorarioBloqueado, TipoConsulta


class ConsultaRapidaForm(forms.Form):
    """
    Formulário do modal de criação rápida, clicando num horário vazio da
    agenda. Aceita uma paciente já cadastrada (campo `paciente`) OU os dados
    básicos para cadastrar uma paciente nova na hora (`nova_paciente_nome` +
    `nova_paciente_telefone`) — exatamente um dos dois precisa vir preenchido.
    """

    paciente = forms.ModelChoiceField(queryset=Paciente.objects.none(), required=False)
    nova_paciente_nome = forms.CharField(max_length=150, required=False)
    nova_paciente_telefone = forms.CharField(max_length=20, required=False)

    profissional = forms.ModelChoiceField(queryset=Profissional.objects.none())
    tipo_consulta = forms.ModelChoiceField(queryset=TipoConsulta.objects.none())
    data = forms.DateField()
    hora = forms.TimeField()
    duracao_minutos = forms.IntegerField(min_value=5, initial=30)
    valor = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False,
        help_text="Preenchido automaticamente pelo tipo de consulta — pode ser personalizado.",
    )
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

    def clean(self):
        cleaned = super().clean()
        paciente = cleaned.get("paciente")
        nome_nova = (cleaned.get("nova_paciente_nome") or "").strip()
        if not paciente and not nome_nova:
            raise forms.ValidationError(
                "Selecione uma paciente existente ou informe o nome da nova paciente."
            )
        return cleaned


class ConsultaEditarForm(forms.ModelForm):
    """
    Corrige dados da consulta já agendada — ex.: profissional errado (Fábio
    x Cláudia) ou data errada. paciente e status ficam de fora: trocar de
    paciente é uma operação bem maior, e status já tem os botões próprios
    (marcar realizada/cancelar) na tela da consulta.
    """

    data_hora = forms.DateTimeField(
        label="Data e hora", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    )

    class Meta:
        model = Consulta
        fields = ["profissional", "tipo_consulta", "data_hora", "duracao_minutos", "valor", "motivo", "observacoes"]
        widgets = {
            "motivo": forms.TextInput(),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]
        organizacao = organizacao or (self.instance.organizacao if self.instance and self.instance.pk else None)
        self.fields["profissional"].queryset = Profissional.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["tipo_consulta"].queryset = TipoConsulta.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("ordem", "nome")


class BloqueioRapidoForm(forms.Form):
    """
    Formulário do modal de bloqueio rápido de horário, aberto ao clicar num
    horário vazio da agenda e escolher "Bloquear horário" em vez de agendar
    uma consulta — sem precisar informar nenhuma paciente.
    """

    profissional = forms.ModelChoiceField(queryset=Profissional.objects.none())
    motivo = forms.ChoiceField(choices=HorarioBloqueado.Motivo.choices)
    data = forms.DateField()
    hora = forms.TimeField()
    duracao_minutos = forms.IntegerField(min_value=5, initial=30)
    observacoes = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profissional"].queryset = Profissional.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
