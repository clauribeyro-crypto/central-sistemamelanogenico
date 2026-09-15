from django import forms

from agenda.models import TipoConsulta

from .models import FaseModulacao, Programa


class TipoConsultaForm(forms.ModelForm):
    class Meta:
        model = TipoConsulta
        fields = ["nome", "cor", "duracao_padrao_minutos", "valor", "ordem", "ativo"]
        widgets = {
            "cor": forms.TextInput(attrs={"type": "color"}),
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Consulta inicial"}),
        }
        help_texts = {
            "valor": "Valor cobrado. Deixe em branco se esse tipo não gerar cobrança automática.",
        }


class ProgramaForm(forms.ModelForm):
    class Meta:
        model = Programa
        fields = [
            "nome", "duracao_meses", "valor", "valor_a_vista", "parcelamento_max",
            "qtd_consultas", "qtd_modulacoes", "qtd_kits",
            "produtos_incluidos", "horario_suporte", "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Programa de 3 meses"}),
        }


class PlanoFaseForm(forms.ModelForm):
    class Meta:
        model = FaseModulacao
        fields = ["plano", "data_inicio"]
        widgets = {
            "plano": forms.Textarea(attrs={"rows": 6}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
        }


class AvaliacaoFaseForm(forms.ModelForm):
    class Meta:
        model = FaseModulacao
        fields = ["resultado", "principais_melhoras", "o_que_trabalhar"]
        widgets = {
            "principais_melhoras": forms.Textarea(attrs={"rows": 3}),
            "o_que_trabalhar": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # blank=True no modelo é só pra permitir fase ainda não avaliada — ao
        # concluir a fase, escolher o resultado é obrigatório.
        self.fields["resultado"].required = True
