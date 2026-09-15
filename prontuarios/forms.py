from django import forms

from agenda.models import Consulta
from profissionais.models import Profissional

from .models import Anamnese, Atendimento

CAMPOS_TEXTO_LONGO = (
    "queixa_principal", "historico_atual", "exame_fisico",
    "diagnostico", "conduta", "prescricao", "observacoes",
)

CAMPOS_ANAMNESE = (
    "melasma_pele", "intestino", "estomago_digestao", "figado_vesicula",
    "hormonal_ciclo", "sono", "alimentacao", "medicamentos",
    "historico_saude", "sinais_sintomas", "observacoes_profissional",
)


class AtendimentoForm(forms.ModelForm):
    class Meta:
        model = Atendimento
        fields = [
            "profissional", "consulta", "data_hora",
            "queixa_principal", "historico_atual", "exame_fisico",
            "diagnostico", "conduta", "prescricao", "observacoes",
        ]
        labels = {
            "historico_atual": "História da doença atual",
            "conduta": "Conduta/procedimentos realizados",
        }
        widgets = {
            "data_hora": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            **{campo: forms.Textarea(attrs={"rows": 3}) for campo in CAMPOS_TEXTO_LONGO},
        }

    def __init__(self, *args, organizacao=None, paciente=None, **kwargs):
        super().__init__(*args, **kwargs)
        # datetime-local não usa nenhum dos formatos padrão do Django (que
        # são separados por espaço, não por "T") — sem isso o form recusa
        # qualquer valor vindo do próprio widget.
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["profissional"].queryset = Profissional.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["consulta"].queryset = Consulta.objects.filter(
            organizacao=organizacao, paciente=paciente
        ).order_by("-data_hora")
        self.fields["consulta"].required = False
        self.fields["consulta"].help_text = "Opcional — vincule à consulta agendada que originou este atendimento."


class AnamneseForm(forms.ModelForm):
    class Meta:
        model = Anamnese
        fields = list(CAMPOS_ANAMNESE)
        widgets = {campo: forms.Textarea(attrs={"rows": 3}) for campo in CAMPOS_ANAMNESE}
