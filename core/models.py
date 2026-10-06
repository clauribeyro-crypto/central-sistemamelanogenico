from decimal import Decimal

from django.db import models

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
