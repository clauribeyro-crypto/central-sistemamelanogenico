from django.db import models
from django.urls import reverse


class Paciente(models.Model):
    class Sexo(models.TextChoices):
        FEMININO = "F", "Feminino"
        MASCULINO = "M", "Masculino"
        OUTRO = "O", "Outro"

    nome = models.CharField("nome completo", max_length=150)
    cpf = models.CharField(
        "CPF", max_length=14, unique=True, blank=True, null=True,
        help_text="Opcional, mas evita cadastros duplicados.",
    )
    data_nascimento = models.DateField("data de nascimento", blank=True, null=True)
    sexo = models.CharField(max_length=1, choices=Sexo.choices, blank=True)

    telefone = models.CharField("telefone/WhatsApp", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)

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

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("pacientes:detalhe", args=[self.pk])
