from django.db import models
from django.utils import timezone

from contas.models import ModeloDaOrganizacao


class Paciente(ModeloDaOrganizacao):
    class Sexo(models.TextChoices):
        FEMININO = "F", "Feminino"
        MASCULINO = "M", "Masculino"
        OUTRO = "O", "Outro"

    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField(
        "CPF", max_length=14, blank=True, null=True,
        help_text="Opcional, mas evita cadastros duplicados.",
    )
    data_nascimento = models.DateField("data de nascimento", blank=True, null=True)
    sexo = models.CharField(max_length=1, choices=Sexo.choices, blank=True)

    telefone = models.CharField("telefone/WhatsApp", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    cidade = models.CharField(max_length=100, blank=True, help_text="Ex.: Belo Horizonte, MG")
    profissao = models.CharField(max_length=100, blank=True)

    historico_saude = models.TextField(
        "histórico de saúde",
        blank=True,
        help_text="Alergias, comorbidades, medicações em uso, observações gerais.",
    )
    observacoes = models.TextField("observações administrativas", blank=True)

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "cpf"],
                condition=models.Q(cpf__isnull=False) & ~models.Q(cpf=""),
                name="cpf_unico_por_organizacao",
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def idade(self):
        if not self.data_nascimento:
            return None
        hoje = timezone.localdate()
        anos = hoje.year - self.data_nascimento.year
        if (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day):
            anos -= 1
        return anos

    @property
    def acompanhamento_atual(self):
        from programas.models import Acompanhamento
        return self.acompanhamentos.filter(
            status__in=Acompanhamento.STATUS_ATIVOS
        ).order_by("-data_inicio").first()
