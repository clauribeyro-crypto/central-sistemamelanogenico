from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from agenda.models import Consulta
from contas.models import ModeloDaOrganizacao
from pacientes.models import Paciente


class Servico(ModeloDaOrganizacao):
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


class Pagamento(ModeloDaOrganizacao):
    class FormaPagamento(models.TextChoices):
        DINHEIRO = "DINHEIRO", "Dinheiro"
        PIX = "PIX", "Pix"
        DEBITO = "DEBITO", "Cartão de débito"
        CREDITO = "CREDITO", "Cartão de crédito"
        CONVENIO = "CONVENIO", "Convênio/plano de saúde"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PARCIAL = "PARCIAL", "Parcial"
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
    acompanhamento = models.ForeignKey(
        "programas.Acompanhamento",
        on_delete=models.SET_NULL,
        related_name="pagamentos",
        blank=True,
        null=True,
        help_text="Programa de acompanhamento ao qual este pagamento pertence, se houver.",
    )

    valor = models.DecimalField("valor total", max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(
        max_length=20, choices=FormaPagamento.choices, blank=True,
        help_text="Preenchida automaticamente com a forma do recebimento mais recente.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE,
        help_text="Calculado automaticamente a partir dos recebimentos registrados.",
    )

    data_vencimento = models.DateField(blank=True, null=True)
    data_pagamento = models.DateField(
        blank=True, null=True,
        help_text="Preenchida automaticamente quando o valor total é quitado.",
    )
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "pagamentos"
        ordering = ["-data_vencimento", "-criado_em"]

    def __str__(self):
        return f"{self.paciente} - R$ {self.valor} ({self.get_status_display()})"

    @property
    def total_recebido(self):
        return self.recebimentos.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    @property
    def saldo_pendente(self):
        saldo = self.valor - self.total_recebido
        return saldo if saldo > 0 else Decimal("0.00")

    def recalcular_status(self):
        """
        Recalcula status/forma_pagamento/data_pagamento a partir da soma dos
        recebimentos parciais. Nunca mexe num lançamento cancelado — cancelar
        é sempre uma decisão manual (ou da sincronização com a Agenda), não
        algo que a chegada/remoção de um recebimento deva desfazer sozinha.
        """
        if self.status == self.Status.CANCELADO:
            return

        total = self.total_recebido
        if total <= 0:
            novo_status = self.Status.PENDENTE
        elif total < self.valor:
            novo_status = self.Status.PARCIAL
        else:
            novo_status = self.Status.PAGO

        ultimo_recebimento = self.recebimentos.order_by("-data", "-criado_em").first()

        self.status = novo_status
        self.forma_pagamento = ultimo_recebimento.forma_pagamento if ultimo_recebimento else ""
        self.data_pagamento = ultimo_recebimento.data if novo_status == self.Status.PAGO else None
        self.save(update_fields=["status", "forma_pagamento", "data_pagamento", "atualizado_em"])


class Recebimento(ModeloDaOrganizacao):
    """
    Um recebimento parcial (ou único, se for o caso) dentro de um lançamento
    do Financeiro — permite dividir o valor total em partes, cada uma com
    sua própria forma de pagamento e data (ex.: entrada por Pix, restante em
    dinheiro no dia da consulta).
    """

    pagamento = models.ForeignKey(Pagamento, on_delete=models.CASCADE, related_name="recebimentos")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pagamento = models.CharField(max_length=20, choices=Pagamento.FormaPagamento.choices)
    data = models.DateField(default=timezone.localdate)
    observacoes = models.CharField(max_length=255, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recebimento"
        verbose_name_plural = "recebimentos"
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"R$ {self.valor} ({self.get_forma_pagamento_display()}) em {self.data:%d/%m/%Y}"
