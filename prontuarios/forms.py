from django import forms

from agenda.models import Consulta
from profissionais.models import Profissional

from .models import SATISFACOES, SECOES_ANAMNESE, SECOES_CHECKIN, Anamnese, Atendimento, Documento, RegistroEvolucao

CAMPOS_TEXTO_LONGO = (
    "queixa_principal", "historico_atual", "exame_fisico",
    "diagnostico", "conduta", "prescricao", "observacoes",
)

# Ordem completa dos campos da anamnese, achatando as 15 seções — usada pelo
# form e, junto com SECOES_ANAMNESE, pelos templates (público e interno).
CAMPOS_ANAMNESE = [
    campo
    for secao in SECOES_ANAMNESE
    for campo in secao["campos"] + ([secao["satisfacao"]] if secao["satisfacao"] else [])
]

_CAMPOS_TEXTAREA = (
    "tratamentos_anteriores", "rotina_matinal", "cirurgias_previas",
    "tratamento_medico_atual", "outras_doencas", "outros_sintomas_doencas",
    "orgaos_mais_atencao",
)
_CAMPOS_SATISFACAO = [campo for campo, _ in SATISFACOES]

# Ordem completa dos campos do check-in, achatando as 4 seções (campos
# específicos + melhora + observação) — mesma lógica de CAMPOS_ANAMNESE,
# usada pelo form e pelos templates (público e manual).
CAMPOS_CHECKIN = [
    campo
    for secao in SECOES_CHECKIN
    for campo in secao["campos"] + [secao["melhora"], secao["observacao"]]
]
_CAMPOS_ESCALA_CHECKIN = (
    "distensao_abdominal", "plenitude_pos_comer", "dor_desconforto",
    "energia_acordar", "energia_apos_almoco", "energia_fim_dia", "qualidade_sono",
    "estado_pele", "equilibrio_emocional", "equilibrio_hormonal", "disposicao_geral",
    "melhora_intestino", "melhora_digestao", "melhora_energia", "melhora_sono",
    "melhora_pele", "melhora_emocional", "melhora_hormonal", "melhora_disposicao",
)
_CAMPOS_OBSERVACAO_CHECKIN = (
    "observacao_intestino", "observacao_digestao", "observacao_energia", "observacao_sono",
    "observacao_pele", "observacao_emocional", "observacao_hormonal", "observacao_disposicao",
)
# Lista de seleção em vez de campo numérico — em alguns celulares o teclado
# numérico do input type="number" trava ou não abre; escolher de uma lista
# de 0 a 10 funciona em qualquer aparelho, sem precisar digitar nada.
_ESCALA_CHOICES = [("", "—")] + [(i, str(i)) for i in range(11)]


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
        fields = CAMPOS_ANAMNESE
        widgets = {
            **{campo: forms.Textarea(attrs={"rows": 3}) for campo in _CAMPOS_TEXTAREA},
            **{
                campo: forms.NumberInput(attrs={"min": 0, "max": 10})
                for campo in _CAMPOS_SATISFACAO
            },
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
        }


class RegistroEvolucaoForm(forms.ModelForm):
    class Meta:
        model = RegistroEvolucao
        fields = CAMPOS_CHECKIN
        widgets = {
            **{
                campo: forms.Select(choices=_ESCALA_CHOICES)
                for campo in _CAMPOS_ESCALA_CHECKIN
            },
            **{
                campo: forms.Textarea(attrs={"rows": 2})
                for campo in _CAMPOS_OBSERVACAO_CHECKIN
            },
            "vezes_acordou_noite": forms.NumberInput(attrs={"min": 0}),
        }


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["nome", "tipo", "arquivo", "observacoes"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}
