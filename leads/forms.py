from django import forms

from agenda.models import TipoConsulta
from profissionais.models import Profissional

from .models import Lead, MotivoPerda, Origem


class NovoLeadForm(forms.ModelForm):
    """Cadastro rápido de lead direto no board do CRM ("+ Novo lead")."""

    class Meta:
        model = Lead
        fields = ["nome", "whatsapp", "telefone", "cidade", "estado", "origem"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "whatsapp": forms.TextInput(attrs={"placeholder": "(11) 91234-5678"}),
            "telefone": forms.TextInput(attrs={"placeholder": "Opcional"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Ex.: São Paulo"}),
            "estado": forms.TextInput(attrs={"placeholder": "UF", "maxlength": 2}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origem"].queryset = Origem.objects.filter(organizacao=organizacao, ativo=True)

    def clean_estado(self):
        return self.cleaned_data["estado"].upper()


class PausarCadenciaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo da pausa", max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Pediu para ser chamada semana que vem"}),
    )
    data_retomada_prevista = forms.DateField(
        label="Retomar em", widget=forms.DateInput(attrs={"type": "date"})
    )
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class PerderLeadForm(forms.Form):
    motivo = forms.ModelChoiceField(label="Motivo da perda", queryset=MotivoPerda.objects.none())
    detalhe = forms.CharField(
        label="Detalhe (obrigatório se o motivo for 'Outro')",
        required=False, widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].queryset = MotivoPerda.objects.filter(
            organizacao=organizacao, ativo=True
        )

    def clean(self):
        cleaned = super().clean()
        motivo = cleaned.get("motivo")
        if motivo and motivo.nome.strip().lower() == "outro" and not cleaned.get("detalhe"):
            self.add_error("detalhe", "Descreva o motivo, já que selecionou 'Outro'.")
        return cleaned


class AgendarConsultaForm(forms.Form):
    profissional = forms.ModelChoiceField(queryset=Profissional.objects.none())
    tipo_consulta = forms.ModelChoiceField(queryset=TipoConsulta.objects.none())
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    hora = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    duracao_minutos = forms.IntegerField(initial=30, min_value=5)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profissional"].queryset = Profissional.objects.filter(
            organizacao=organizacao, ativo=True
        )
        self.fields["tipo_consulta"].queryset = TipoConsulta.objects.filter(
            organizacao=organizacao, ativo=True
        )


class EnviarWhatsAppForm(forms.Form):
    texto = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))


class RegistrarLigacaoForm(forms.Form):
    RESULTADO_CHOICES = [
        ("ATENDEU", "Atendeu"),
        ("NAO_ATENDEU", "Não atendeu"),
    ]
    resultado = forms.ChoiceField(choices=RESULTADO_CHOICES, widget=forms.RadioSelect)


class ResultadoContatoForm(forms.Form):
    RESULTADO_CHOICES = [
        ("RESPONDEU", "Respondeu — seguir conversa"),
        ("NAO_RESPONDEU", "Não respondeu"),
    ]
    resultado = forms.ChoiceField(choices=RESULTADO_CHOICES, widget=forms.RadioSelect)
