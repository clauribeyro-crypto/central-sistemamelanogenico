from django.db import models

DIAS_SEMANA = [
    (0, "Segunda-feira"),
    (1, "Terça-feira"),
    (2, "Quarta-feira"),
    (3, "Quinta-feira"),
    (4, "Sexta-feira"),
    (5, "Sábado"),
    (6, "Domingo"),
]


class Profissional(models.Model):
    nome = models.CharField("nome completo", max_length=150)
    especialidade = models.CharField(max_length=100, blank=True)
    registro_conselho = models.CharField(
        "registro no conselho de classe", max_length=50, blank=True,
        help_text="Ex.: CRM, COREN, CRO, etc.",
    )
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "profissional"
        verbose_name_plural = "profissionais"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class HorarioAtendimento(models.Model):
    """Janela recorrente de disponibilidade de um profissional na agenda."""

    profissional = models.ForeignKey(
        Profissional, on_delete=models.CASCADE, related_name="horarios"
    )
    dia_semana = models.IntegerField("dia da semana", choices=DIAS_SEMANA)
    hora_inicio = models.TimeField("início")
    hora_fim = models.TimeField("fim")

    class Meta:
        verbose_name = "horário de atendimento"
        verbose_name_plural = "horários de atendimento"
        ordering = ["profissional", "dia_semana", "hora_inicio"]

    def __str__(self):
        return f"{self.profissional} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fim}"
