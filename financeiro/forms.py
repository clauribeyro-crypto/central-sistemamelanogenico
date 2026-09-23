from decimal import Decimal

from django import forms

from .models import Banco, CategoriaFinanceira, Lancamento, Pagamento, Recebimento


class PagamentoForm(forms.ModelForm):
    # format="%Y-%m-%d" é essencial: sem ele, o widget usa o formato
    # localizado (dd/mm/aaaa em pt-br) no atributo value, que o
    # <input type="date"> do navegador rejeita silenciosamente.
    data_vencimento = forms.DateField(
        label="Vencimento", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Pagamento
        # status, forma_pagamento e data_pagamento não entram aqui — são
        # calculados automaticamente a partir dos recebimentos (ver
        # Pagamento.recalcular_status).
        fields = ["valor", "data_vencimento", "acompanhamento", "observacoes"]
        labels = {"acompanhamento": "Tratamento/programa vinculado"}
        help_texts = {
            "acompanhamento": (
                "A que tratamento essa cobrança pertence. Corrige o caso de um "
                "recebimento ter sido registrado no lançamento errado (ex.: numa "
                "consulta em vez do programa) — o dinheiro já recebido não se "
                "perde, só passa a contar pro tratamento certo."
            ),
        }
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from programas.models import Acompanhamento

        self.fields["acompanhamento"].required = False
        self.fields["acompanhamento"].queryset = Acompanhamento.objects.filter(
            paciente=self.instance.paciente
        ).select_related("programa").order_by("-data_inicio")
        self.fields["acompanhamento"].empty_label = "Nenhum (sem tratamento vinculado)"


class RecebimentoForm(forms.ModelForm):
    data = forms.DateField(
        label="Data", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Recebimento
        fields = ["valor", "forma_pagamento", "data", "observacoes"]
        widgets = {
            "observacoes": forms.TextInput(attrs={"placeholder": "Opcional — ex.: entrada, sinal, restante"}),
        }

    def __init__(self, *args, pagamento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pagamento = pagamento
        if pagamento is not None:
            self.fields["valor"].initial = pagamento.saldo_pendente

    def clean_valor(self):
        valor = self.cleaned_data["valor"]
        if valor <= 0:
            raise forms.ValidationError("O valor precisa ser maior que zero.")
        if self.pagamento is not None and valor > self.pagamento.saldo_pendente:
            raise forms.ValidationError(
                f"Esse valor é maior que o saldo pendente (R$ {self.pagamento.saldo_pendente:.2f})."
            )
        return valor


class BancoForm(forms.ModelForm):
    class Meta:
        model = Banco
        fields = ["nome", "ativo"]

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao = organizacao

    def clean_nome(self):
        # organizacao não é campo do form (é preenchida na view), então o
        # validate_unique automático do ModelForm não pega a constraint
        # organizacao+nome — sem isso, um nome repetido derruba o app com
        # IntegrityError em vez de mostrar um erro de formulário.
        nome = self.cleaned_data["nome"]
        if Banco.objects.filter(organizacao=self.organizacao, nome=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe um banco com esse nome.")
        return nome


class CategoriaFinanceiraForm(forms.ModelForm):
    class Meta:
        model = CategoriaFinanceira
        fields = ["nome", "grupo", "ativo"]

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao = organizacao

    def clean_nome(self):
        nome = self.cleaned_data["nome"]
        if CategoriaFinanceira.objects.filter(
            organizacao=self.organizacao, nome=nome
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma categoria com esse nome.")
        return nome


class LancamentoForm(forms.ModelForm):
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    class Meta:
        model = Lancamento
        fields = ["data", "descricao", "categoria", "banco", "valor", "status", "observacoes"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaFinanceira.objects.filter(
            organizacao=organizacao, ativo=True
        )
        self.fields["banco"].queryset = Banco.objects.filter(organizacao=organizacao, ativo=True)
        self.fields["banco"].required = False
