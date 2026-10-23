from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from contas.models import Organizacao


class VendaKitMentora(models.Model):
    """
    Venda de kit/produto da Cláudia pra uma organização mentorada — negócio à
    parte da clínica em si (a mentorada compra pra revender às próprias
    pacientes). Só a administradora geral (mentora) vê isso, em qualquer
    organização — por isso mora aqui no core, não dentro de uma organização.
    """

    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name="vendas_kit_como_fornecedora",
        help_text="Organização vendedora (quem está enviando o produto) — normalmente a sua própria.",
    )
    mentorada = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name="compras_kit_mentora"
    )
    produtos = models.ManyToManyField(
        "estoque.Produto", blank=True, related_name="vendas_kit_mentora_m2m",
        help_text=(
            "Produtos do seu estoque que fazem parte dessa venda — marque só um pra uma venda avulsa, "
            "ou mais de um quando for um kit. A quantidade abaixo desconta de cada produto marcado."
        ),
    )
    kit_nome = models.CharField(
        "kit", max_length=150, blank=True,
        help_text="Nome livre, pra vendas que não correspondem a produto nenhum do seu estoque. Deixe em branco se marcou produto(s) acima.",
    )
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField("valor por kit", max_digits=10, decimal_places=2)
    data_venda = models.DateField()
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    data_pagamento_restante = models.DateField(
        null=True, blank=True,
        help_text="Quando o saldo (se houver) deve ser pago.",
    )
    previsao_proxima_compra = models.DateField(
        null=True, blank=True,
        help_text="Pra quando você espera que essa mentorada precise comprar de novo.",
    )
    observacoes = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "venda de kit pra mentorada"
        verbose_name_plural = "vendas de kit pras mentoradas"
        ordering = ["-data_venda", "-criado_em"]

    def __str__(self):
        return f"{self.mentorada} — {self.quantidade}x {self.nome_exibicao} ({self.data_venda:%d/%m/%Y})"

    @property
    def nome_exibicao(self):
        if self.kit_nome:
            return self.kit_nome
        nomes = [p.nome for p in self.produtos.all()]
        return " + ".join(nomes) if nomes else "—"

    @property
    def valor_total(self):
        return self.valor_unitario * self.quantidade

    @property
    def saldo_pendente(self):
        saldo = self.valor_total - self.valor_pago
        return saldo if saldo > 0 else Decimal("0.00")


class ContratoMentoria(models.Model):
    """
    O contrato de mentoria entre a Cláudia e uma organização mentorada —
    valor total combinado, pago aos poucos conforme a mentorada vai batendo
    as próprias metas (não é um parcelamento fixo). Uma mentorada tem um
    contrato só.
    """

    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name="contratos_mentoria_como_fornecedora",
        help_text="Organização que está vendendo a mentoria — normalmente a sua própria.",
    )
    mentorada = models.OneToOneField(
        Organizacao, on_delete=models.CASCADE, related_name="contrato_mentoria",
    )
    valor_total = models.DecimalField(
        "valor total da mentoria", max_digits=10, decimal_places=2,
        help_text="Valor total combinado com essa mentorada (ex.: R$ 30.000).",
    )
    data_inicio = models.DateField(default=timezone.localdate)
    observacoes = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "contrato de mentoria"
        verbose_name_plural = "contratos de mentoria"
        ordering = ["mentorada__nome"]

    def __str__(self):
        return f"Mentoria de {self.mentorada} (R$ {self.valor_total})"

    @property
    def total_pago(self):
        return self.parcelas.filter(data_pagamento__isnull=False).aggregate(
            total=Sum("valor")
        )["total"] or Decimal("0.00")

    @property
    def saldo_pendente(self):
        saldo = self.valor_total - self.total_pago
        return saldo if saldo > 0 else Decimal("0.00")


class ParcelaMentoria(models.Model):
    """
    Um valor recebido (ou ainda só previsto) do contrato de mentoria de uma
    organização. Deixar "data_pagamento" em branco lança a parcela como uma
    previsão futura (ex.: "vai pagar mais R$ 5.000 esse mês"); preencher
    marca que o valor já entrou de fato.
    """

    contrato = models.ForeignKey(ContratoMentoria, on_delete=models.CASCADE, related_name="parcelas")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_prevista = models.DateField(
        null=True, blank=True,
        help_text="Quando você espera receber esse valor. Pode deixar em branco se já foi pago.",
    )
    data_pagamento = models.DateField(
        null=True, blank=True,
        help_text="Preencha quando o valor realmente entrar. Deixe em branco pra lançar como previsão futura.",
    )
    observacoes = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "parcela de mentoria"
        verbose_name_plural = "parcelas de mentoria"
        ordering = ["-criado_em"]

    def __str__(self):
        status = "paga" if self.data_pagamento else "prevista"
        return f"R$ {self.valor} ({status}) — {self.contrato.mentorada}"

    @property
    def paga(self):
        return self.data_pagamento is not None

    @property
    def atrasada(self):
        return not self.paga and bool(self.data_prevista) and self.data_prevista < timezone.localdate()


def totais_mentoria_no_periodo(org, data_inicio, data_fim):
    """
    Total efetivamente recebido de contratos de mentoria no período (pela
    data de pagamento de cada parcela) — receita de outro negócio (a
    mentoria em si), separada da meta de faturamento da clínica.
    """
    parcelas = ParcelaMentoria.objects.filter(
        contrato__organizacao=org, data_pagamento__gte=data_inicio, data_pagamento__lte=data_fim,
    )
    total_recebido = parcelas.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")
    return {"total_recebido": total_recebido, "qtd": parcelas.count()}


def totais_vendas_kit_mentora_no_periodo(org, data_inicio, data_fim):
    """
    Total vendido e efetivamente recebido de kits pras mentoradas no
    período (pela data da venda) — é receita de outro negócio (venda no
    atacado pras mentoradas revenderem), por isso fica separada da meta de
    faturamento da clínica em vez de somar junto.
    """
    vendas = VendaKitMentora.objects.filter(
        organizacao=org, data_venda__gte=data_inicio, data_venda__lte=data_fim,
    )
    total_vendido = Decimal("0.00")
    total_pago = Decimal("0.00")
    qtd = 0
    for venda in vendas:
        total_vendido += venda.valor_total
        total_pago += venda.valor_pago
        qtd += 1
    return {"total_vendido": total_vendido, "total_pago": total_pago, "qtd": qtd}
