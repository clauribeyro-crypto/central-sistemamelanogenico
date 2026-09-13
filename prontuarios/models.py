from django.db import models

from agenda.models import Consulta
from contas.models import ModeloDaOrganizacao
from pacientes.models import Paciente
from profissionais.models import Profissional


class Atendimento(ModeloDaOrganizacao):
    """Registro de prontuário de um atendimento realizado a um paciente."""

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="atendimentos"
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="atendimentos"
    )
    consulta = models.OneToOneField(
        Consulta,
        on_delete=models.SET_NULL,
        related_name="atendimento",
        blank=True,
        null=True,
        help_text="Consulta agendada que originou este atendimento (opcional).",
    )
    data_hora = models.DateTimeField("data e hora do atendimento")

    queixa_principal = models.TextField(blank=True)
    historico_atual = models.TextField("história da doença atual", blank=True)
    exame_fisico = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    conduta = models.TextField(
        "conduta/procedimentos realizados", blank=True
    )
    prescricao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "atendimento"
        verbose_name_plural = "atendimentos (prontuário)"
        ordering = ["-data_hora"]
        indexes = [
            models.Index(fields=["paciente", "data_hora"]),
        ]

    def __str__(self):
        return f"Atendimento de {self.paciente} em {self.data_hora:%d/%m/%Y %H:%M}"
