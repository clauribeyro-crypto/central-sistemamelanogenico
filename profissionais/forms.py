from django import forms

from .models import Profissional


class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = [
            "nome", "especialidade", "registro_conselho",
            "telefone", "email", "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "especialidade": forms.TextInput(attrs={"placeholder": "Ex.: Dermatologista"}),
            "registro_conselho": forms.TextInput(attrs={"placeholder": "Ex.: CRM 12345"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(11) 91234-5678"}),
        }
