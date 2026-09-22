from django import forms

from agenda.models import TipoConsulta

from .models import Acompanhamento, Feedback, FaseModulacao, FotoEvolucao, Programa


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
            "qtd_consultas", "intervalo_dias_consultas", "qtd_modulacoes", "qtd_kits",
            "produtos_incluidos", "horario_suporte", "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Programa de 3 meses"}),
        }


class AcompanhamentoForm(forms.ModelForm):
    data_inicio = forms.DateField(
        label="Data de início", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Acompanhamento
        # programa fica de fora: trocar de plano não regenera as consultas/kits
        # já criados (ver Acompanhamento.iniciar), então mudar aqui deixaria o
        # checklist do programa dessincronizado. status também fica de fora —
        # tem fluxo próprio (ver mudar_status_acompanhamento).
        fields = ["data_inicio", "valor_contratado", "desconto", "forma_pagamento", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_inicio"].input_formats = ["%Y-%m-%d"]


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


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = [
            "fase", "data_hora", "semana", "relato", "observacao",
            "conduta", "precisou_alterar",
        ]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "relato": forms.Textarea(attrs={"rows": 3}),
            "observacao": forms.Textarea(attrs={"rows": 3}),
            "conduta": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, acompanhamento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_hora"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["fase"].queryset = FaseModulacao.objects.filter(
            modulacao__acompanhamento=acompanhamento
        ).order_by("modulacao__numero", "numero")
        self.fields["fase"].required = False


class FotoEvolucaoForm(forms.ModelForm):
    class Meta:
        model = FotoEvolucao
        fields = ["angulo", "momento", "imagem", "data"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}
