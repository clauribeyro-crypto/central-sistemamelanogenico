from django.db import models

from agenda.models import Consulta
from pacientes.models import Paciente


class Servico(models.Model):
    """Tabela de preços: procedimentos/consultas e seus valores padrão."""

    nome = models.CharField(max_length=150)
    valor_padrao = models.DecimalField(max_digits=10, decimal_places=2)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "serviço"
        verbose_name_plural = "serviços (tabela de preços)"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} (R$ {self.valor_padrao})"


class Pagamento(models.Model):
    class FormaPagamento(models.TextChoices):
        DINHEIRO = "DINHEIRO", "Dinheiro"
        PIX = "PIX", "Pix"
        DEBITO = "DEBITO", "Cartão de débito"
        CREDITO = "CREDITO", "Cartão de crédito"
        CONVENIO = "CONVENIO", "Convênio/plano de saúde"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PAGO = "PAGO", "Pago"
        CANCELADO = "CANCELADO", "Cancelado"

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="pagamentos"
    )
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.SET_NULL,
        related_name="pagamentos",
        blank=True,
        null=True,
    )
    servico = models.ForeignKey(
        Servico, on_delete=models.SET_NULL, blank=True, null=True
    )

    valor = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(
        max_length=20, choices=FormaPagamento.choices, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )

    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(blank=True, null=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"
        ordering = ["-data_vencimento", "-criado_em"]

    def __str__(self):
        return f"{self.paciente} - R$ {self.valor} ({self.get_status_display()})"
