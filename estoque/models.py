import datetime
from decimal import Decimal

from django.db import models
from django.utils import timezone

from contas.models import ModeloDaOrganizacao
from pacientes.models import Paciente


class Produto(ModeloDaOrganizacao):
    """
    Item de estoque em nível único — cada produto pronto (Produto Dia,
    Hidratante, Sabonete...), sem rastrear insumos/matéria-prima separados.
    """

    nome = models.CharField(max_length=150)
    estoque_atual = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(
        default=0,
        help_text="Abaixo disso, o produto aparece como estoque baixo/crítico na Visão geral.",
    )
    preco_pix = models.DecimalField(
        "preço no Pix/dinheiro", max_digits=8, decimal_places=2, default=0,
        help_text="Usado para sugerir o valor ao registrar uma venda — pode ser ajustado na hora.",
    )
    preco_cartao = models.DecimalField(
        "preço no cartão", max_digits=8, decimal_places=2, default=0,
        help_text="Usado para sugerir o valor ao registrar uma venda — pode ser ajustado na hora.",
    )
    duracao_estimada_dias = models.PositiveIntegerField(
        blank=True, null=True,
        help_text=(
            "Quantos dias uma unidade dura em uso — usado pra prever quando a "
            "paciente vai precisar recomprar. Deixe em branco se não se aplica."
        ),
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @property
    def nivel_estoque(self):
        """"OK" / "BAIXO" / "CRITICO" — crítico é zero ou metade (ou menos) do mínimo."""
        if self.estoque_atual <= 0:
            return "CRITICO"
        if self.estoque_minimo and self.estoque_atual <= self.estoque_minimo / 2:
            return "CRITICO"
        if self.estoque_minimo and self.estoque_atual <= self.estoque_minimo:
            return "BAIXO"
        return "OK"


class ProducaoPendente(ModeloDaOrganizacao):
    """
    Reposição de estoque em andamento (manipulação ou compra) — some da lista
    de pendentes quando marcada como pronta, somando ao estoque do produto.
    """

    class Status(models.TextChoices):
        AGUARDANDO_INICIO = "AGUARDANDO_INICIO", "Aguardando início"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em manipulação"
        PRONTO = "PRONTO", "Pronto"

    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="producoes")
    quantidade = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AGUARDANDO_INICIO)
    previsao_conclusao = models.DateField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "produção pendente"
        verbose_name_plural = "produções pendentes"
        ordering = ["previsao_conclusao"]

    def __str__(self):
        return f"{self.quantidade}x {self.produto} ({self.get_status_display()})"

    def marcar_pronto(self):
        self.produto.estoque_atual += self.quantidade
        self.produto.save(update_fields=["estoque_atual"])
        self.status = self.Status.PRONTO
        self.concluido_em = timezone.now()
        self.save(update_fields=["status", "concluido_em"])


class Recompra(ModeloDaOrganizacao):
    """
    Previsão/registro de quando uma paciente precisa comprar de novo um
    produto — gerada automaticamente ao montar um kit (quando o produto tem
    duração estimada) ou lançada manualmente.
    """

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="recompras")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="recompras")
    data_prevista = models.DateField()
    data_realizada = models.DateField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recompra"
        verbose_name_plural = "recompras"
        ordering = ["data_prevista"]

    def __str__(self):
        return f"{self.produto} — {self.paciente} (previsão {self.data_prevista:%d/%m/%Y})"

    @property
    def status(self):
        if self.data_realizada:
            return "REALIZADA"
        dias = (self.data_prevista - timezone.localdate()).days
        if dias < 0:
            return "ATRASADA"
        if dias <= 7:
            return "PROXIMA_DO_PRAZO"
        return "EM_DIA"

    def marcar_comprada(self):
        """Registra a recompra feita hoje e já agenda o próximo ciclo, se o produto tiver duração estimada."""
        hoje = timezone.localdate()
        self.data_realizada = hoje
        self.save(update_fields=["data_realizada"])
        if self.produto.duracao_estimada_dias:
            Recompra.objects.create(
                organizacao=self.organizacao, paciente=self.paciente, produto=self.produto,
                data_prevista=hoje + datetime.timedelta(days=self.produto.duracao_estimada_dias),
            )


class Venda(ModeloDaOrganizacao):
    """
    Uma compra de produtos — reúne vários produtos numa venda só (ver
    ItemVenda), em vez de uma venda por produto. Quando é de uma paciente
    cadastrada, gera um Pagamento no Financeiro (mesmo mecanismo que
    tratamento e consulta já usam), pra dar pra registrar pagamento
    parcelado — uma parte agora, o resto depois. Comprador avulso (não é
    paciente) não gera Pagamento: é tratado como pago na hora, sem
    parcelamento (não tem como cobrar parcela de quem não tem cadastro).
    """

    class FormaPagamento(models.TextChoices):
        PIX = "PIX", "Pix/dinheiro"
        CARTAO = "CARTAO", "Cartão"

    paciente = models.ForeignKey(
        Paciente, on_delete=models.SET_NULL, blank=True, null=True, related_name="compras_produtos",
    )
    nome_comprador_avulso = models.CharField(
        "nome (quem não é paciente cadastrada)", max_length=150, blank=True,
        help_text="Pra quem só quer comprar o produto, sem ser paciente — não cria cadastro nenhum.",
    )
    forma_pagamento = models.CharField(
        max_length=10, choices=FormaPagamento.choices, default=FormaPagamento.PIX,
        help_text="Usada pra calcular o preço de cada item (tabela Pix ou cartão) no momento da venda.",
    )
    data = models.DateField(default=timezone.localdate)
    observacoes = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "venda"
        verbose_name_plural = "vendas"
        ordering = ["-data", "-criado_em"]

    def __str__(self):
        return f"Compra de {self.nome_comprador} em {self.data:%d/%m/%Y}"

    @property
    def nome_comprador(self):
        return self.paciente.nome if self.paciente_id else (self.nome_comprador_avulso or "—")

    @property
    def valor_total(self):
        return sum((item.valor_total for item in self.itens.all()), Decimal("0.00"))

    @property
    def quantidade_total(self):
        return sum((item.quantidade for item in self.itens.all()), 0)


class ItemVenda(ModeloDaOrganizacao):
    """Um produto — com quantidade e preço travado no momento da venda — dentro de uma Venda."""

    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="itens_vendidos")
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "item da venda"
        verbose_name_plural = "itens da venda"

    def __str__(self):
        return f"{self.quantidade}x {self.produto}"

    @property
    def valor_total(self):
        return self.valor_unitario * self.quantidade
