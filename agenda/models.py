from django.db import models

from contas.models import ModeloDaOrganizacao
from pacientes.models import Paciente
from profissionais.models import Profissional


class TipoConsulta(ModeloDaOrganizacao):
    """Tipo de atendimento (consulta inicial, retorno, etc.), com cor própria na agenda."""

    nome = models.CharField(max_length=80)
    cor = models.CharField(
        max_length=7,
        default="#7C3AED",
        help_text="Cor em hexadecimal usada nos blocos e na legenda da agenda. Ex.: #7C3AED",
    )
    duracao_padrao_minutos = models.PositiveIntegerField(default=30)
    valor = models.DecimalField(
        "valor",
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=(
            "Valor cobrado nesse tipo de consulta. Ao agendar uma consulta "
            "desse tipo, esse valor entra automaticamente no Financeiro como "
            "receita prevista (pendente)."
        ),
    )
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "tipo de consulta"
        verbose_name_plural = "tipos de consulta"
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "nome"], name="tipo_consulta_unico_por_organizacao"
            ),
        ]

    def __str__(self):
        return self.nome


class HorarioBloqueado(ModeloDaOrganizacao):
    """Bloqueio de agenda: almoço, reunião, folga, dia sem atendimento, etc."""

    class Motivo(models.TextChoices):
        ALMOCO = "ALMOCO", "Horário de almoço"
        REUNIAO = "REUNIAO", "Reunião"
        COMPROMISSO_PESSOAL = "COMPROMISSO_PESSOAL", "Compromisso pessoal"
        TREINAMENTO = "TREINAMENTO", "Treinamento"
        FERIAS = "FERIAS", "Férias"
        SEM_ATENDIMENTO = "SEM_ATENDIMENTO", "Dia sem atendimento"
        OUTRO = "OUTRO", "Outro"

    profissional = models.ForeignKey(
        Profissional, on_delete=models.CASCADE, related_name="bloqueios"
    )
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    motivo = models.CharField(max_length=25, choices=Motivo.choices)
    observacoes = models.CharField(max_length=255, blank=True)
    cor = models.CharField(max_length=7, default="#EF4444")

    class Meta:
        verbose_name = "horário bloqueado"
        verbose_name_plural = "horários bloqueados"
        ordering = ["inicio"]
        indexes = [models.Index(fields=["profissional", "inicio", "fim"])]

    def __str__(self):
        return f"{self.profissional} bloqueado ({self.get_motivo_display()}) {self.inicio:%d/%m %H:%M}-{self.fim:%H:%M}"


class Consulta(ModeloDaOrganizacao):
    class Status(models.TextChoices):
        AGENDADA = "AGENDADA", "Agendada"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        REALIZADA = "REALIZADA", "Realizada"
        REAGENDADA = "REAGENDADA", "Reagendada"
        CANCELADA = "CANCELADA", "Cancelada"
        NAO_COMPARECEU = "NAO_COMPARECEU", "Não compareceu"

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="consultas"
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="consultas"
    )
    tipo_consulta = models.ForeignKey(
        TipoConsulta, on_delete=models.PROTECT, related_name="consultas"
    )
    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.SET_NULL,
        related_name="consultas",
        blank=True,
        null=True,
        help_text="Lead do CRM que originou este agendamento, se houver.",
    )
    reagendada_de = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="reagendamentos",
        blank=True,
        null=True,
        help_text="Consulta original, quando esta é resultado de um reagendamento.",
    )

    data_hora = models.DateTimeField("data e hora")
    duracao_minutos = models.PositiveIntegerField("duração (min)", default=30)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.AGENDADA
    )
    motivo = models.CharField("motivo da consulta", max_length=255, blank=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "consulta"
        verbose_name_plural = "consultas"
        ordering = ["data_hora"]
        indexes = [
            models.Index(fields=["profissional", "data_hora"]),
            models.Index(fields=["paciente", "data_hora"]),
        ]

    def __str__(self):
        return f"{self.paciente} com {self.profissional} em {self.data_hora:%d/%m/%Y %H:%M}"
