from django import forms

from pacientes.models import Paciente

from .models import Produto, ProducaoPendente, Recompra


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ["nome", "estoque_atual", "estoque_minimo", "duracao_estimada_dias", "ativo"]


class EntradaEstoqueForm(forms.Form):
    quantidade = forms.IntegerField(min_value=1, label="Quantidade a adicionar")


class ProducaoPendenteForm(forms.ModelForm):
    class Meta:
        model = ProducaoPendente
        fields = ["produto", "quantidade", "status", "previsao_conclusao"]
        widgets = {"previsao_conclusao": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["produto"].queryset = Produto.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")


class RecompraForm(forms.ModelForm):
    class Meta:
        model = Recompra
        fields = ["paciente", "produto", "data_prevista"]
        widgets = {"data_prevista": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["produto"].queryset = Produto.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
