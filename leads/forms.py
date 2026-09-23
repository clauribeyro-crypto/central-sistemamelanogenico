from django import forms

from agenda.models import TipoConsulta
from profissionais.models import Profissional

from .models import Lead, MotivoPerda, Origem, RegistroMarketingDiario, RegistroSocialSelling


class OrigemForm(forms.ModelForm):
    class Meta:
        model = Origem
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
        if Origem.objects.filter(organizacao=self.organizacao, nome=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma origem com esse nome.")
        return nome


class RegistroSocialSellingForm(forms.ModelForm):
    class Meta:
        model = RegistroSocialSelling
        fields = ["seguidores_novos", "pessoas_chamadas", "pessoas_responderam", "contatos_conseguidos"]
        widgets = {
            campo: forms.NumberInput(attrs={
                "min": 0, "inputmode": "numeric",
                "style": "width:80px; padding:.4rem; border:1px solid #ddd5ee; border-radius:8px;",
            })
            for campo in ["seguidores_novos", "pessoas_chamadas", "pessoas_responderam", "contatos_conseguidos"]
        }


class RegistroMarketingDiarioForm(forms.ModelForm):
    class Meta:
        model = RegistroMarketingDiario
        fields = ["data", "investimento", "impressoes", "cliques", "pageviews"]
        widgets = {
            "data": forms.HiddenInput(),
            "investimento": forms.NumberInput(attrs={
                "min": 0, "step": "0.01", "inputmode": "decimal",
                "style": "width:100px; padding:.3rem; border:1px solid #ddd5ee; border-radius:6px;",
            }),
            **{
                campo: forms.NumberInput(attrs={
                    "min": 0, "inputmode": "numeric",
                    "style": "width:90px; padding:.3rem; border:1px solid #ddd5ee; border-radius:6px;",
                })
                for campo in ["impressoes", "cliques", "pageviews"]
            },
        }


class _LeadContatoFormMixin:
    """
    Exige pelo menos um jeito de contato (WhatsApp ou Instagram) — um lead
    abordado primeiro pelo Instagram pode não ter telefone ainda, mas
    precisa de algum contato pra não ficar impossível de falar com ele.
    """

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("whatsapp") and not cleaned.get("instagram"):
            raise forms.ValidationError("Informe pelo menos o WhatsApp ou o Instagram do lead.")
        return cleaned

    def clean_estado(self):
        return self.cleaned_data["estado"].upper()


class NovoLeadForm(_LeadContatoFormMixin, forms.ModelForm):
    """Cadastro rápido de lead direto no board do CRM ("+ Novo lead")."""

    class Meta:
        model = Lead
        fields = ["nome", "whatsapp", "instagram", "telefone", "cidade", "estado", "origem"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "whatsapp": forms.TextInput(attrs={"placeholder": "(11) 91234-5678"}),
            "instagram": forms.TextInput(attrs={"placeholder": "@usuario"}),
            "telefone": forms.TextInput(attrs={"placeholder": "Opcional"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Ex.: São Paulo"}),
            "estado": forms.TextInput(attrs={"placeholder": "UF", "maxlength": 2}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origem"].queryset = Origem.objects.filter(organizacao=organizacao, ativo=True)


class EditarLeadForm(_LeadContatoFormMixin, forms.ModelForm):
    """Editar os dados de contato de um lead já existente (ex.: completar o telefone depois)."""

    class Meta:
        model = Lead
        fields = ["nome", "whatsapp", "instagram", "telefone", "cidade", "estado", "origem"]
        widgets = {
            "whatsapp": forms.TextInput(attrs={"placeholder": "(11) 91234-5678"}),
            "instagram": forms.TextInput(attrs={"placeholder": "@usuario"}),
            "telefone": forms.TextInput(attrs={"placeholder": "Opcional"}),
            "estado": forms.TextInput(attrs={"maxlength": 2}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origem"].queryset = Origem.objects.filter(organizacao=organizacao, ativo=True)


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
