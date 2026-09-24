from django import forms
from django.forms import formset_factory
from django.utils import timezone

from pacientes.models import Paciente

from .models import Produto, ProducaoPendente, Recompra, Venda


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            "nome", "preco_pix", "preco_cartao",
            "estoque_atual", "estoque_minimo", "duracao_estimada_dias", "ativo",
        ]


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


class VendaForm(forms.ModelForm):
    """Cabeçalho da compra — quem comprou, forma de pagamento (pra calcular o preço) e quanto já recebeu."""

    valor_recebido_agora = forms.DecimalField(
        label="Valor recebido agora", max_digits=10, decimal_places=2, required=False, min_value=0,
        help_text=(
            "Só vale pra paciente cadastrada (compra parcelada). Deixe em branco se ainda não "
            "recebeu nada — dá pra registrar depois, no Financeiro. Pra quem não é paciente, a "
            "compra é sempre tratada como paga na hora, sem controle de parcela."
        ),
        widget=forms.NumberInput(attrs={"min": 0, "step": "0.01", "inputmode": "decimal"}),
    )

    class Meta:
        model = Venda
        fields = ["paciente", "nome_comprador_avulso", "forma_pagamento", "desconto", "data", "observacoes"]
        widgets = {
            # format="%Y-%m-%d" força o formato que o <input type="date"> do
            # navegador entende — sem isso, o formato padrão de pt-br
            # (dd/mm/aaaa) faz o navegador simplesmente ignorar o valor
            # inicial e mostrar o campo em branco.
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "desconto": forms.NumberInput(attrs={"min": 0, "step": "0.01", "inputmode": "decimal"}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paciente"].queryset = Paciente.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")
        self.fields["paciente"].required = False
        if not self.is_bound:
            self.fields["data"].initial = timezone.localdate()


class ItemVendaForm(forms.Form):
    """Uma linha do carrinho — produto e quantidade. Linha em branco é ignorada."""

    produto = forms.ModelChoiceField(queryset=Produto.objects.none(), required=False, label="Produto")
    quantidade = forms.IntegerField(min_value=1, initial=1, required=False, label="Qtd.")

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["produto"].queryset = Produto.objects.filter(
            organizacao=organizacao, ativo=True
        ).order_by("nome")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("produto") and not cleaned.get("quantidade"):
            self.add_error("quantidade", "Informe a quantidade.")
        return cleaned


ItemVendaFormSet = formset_factory(ItemVendaForm, extra=6)
