from django import forms

from agenda.models import TipoConsulta

from .models import Programa


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
