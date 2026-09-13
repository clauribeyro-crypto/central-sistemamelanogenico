from django.db import models
from django.urls import reverse

from pacientes.models import Paciente
from profissionais.models import Profissional


class Consulta(models.Model):
    class Status(models.TextChoices):
        AGENDADA = "AGENDADA", "Agendada"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"
        FALTOU = "FALTOU", "Paciente faltou"

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="consultas"
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="consultas"
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

    def get_absolute_url(self):
        return reverse("agenda:detalhe", args=[self.pk])
