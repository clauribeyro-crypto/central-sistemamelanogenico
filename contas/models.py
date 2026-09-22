from django.contrib.auth.models import AbstractUser
from django.db import models


class Organizacao(models.Model):
    """
    Uma clínica/mentorada dentro do sistema. Todo o resto dos dados (leads,
    pacientes, agenda, financeiro...) pertence a uma Organizacao, e uma
    organização nunca enxerga os dados de outra.
    """

    nome = models.CharField(max_length=150)
    slug = models.SlugField(
        unique=True,
        help_text="Identificador curto usado internamente, sem espaços. Ex.: clinica-exemplo",
    )
    ativo = models.BooleanField(default=True)

    # Configurações da agenda desta organização.
    agenda_hora_inicio = models.TimeField(default="08:00")
    agenda_hora_fim = models.TimeField(default="18:00")
    agenda_intervalo_minutos = models.PositiveIntegerField(
        default=30,
        help_text="Intervalo entre horários na grade da agenda (em minutos).",
    )

    dias_lead_parado = models.PositiveIntegerField(
        default=3,
        help_text=(
            "Quantos dias sem nenhuma atualização de status fazem um lead "
            "aparecer no card \"Leads parados\" da tela inicial."
        ),
    )

    saldo_inicial_financeiro = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Saldo em caixa antes do primeiro lançamento registrado no sistema — base pro saldo acumulado do Controle Financeiro.",
    )

    modulo_leads_ativo = models.BooleanField(
        default=True, verbose_name="módulo CRM de leads ativo",
        help_text="Desmarque para esconder o CRM de leads do menu dessa organização.",
    )
    modulo_financeiro_ativo = models.BooleanField(
        default=True, verbose_name="módulo Controle Financeiro ativo",
        help_text="Desmarque para esconder o Controle Financeiro do menu dessa organização.",
    )
    modulo_programas_ativo = models.BooleanField(
        default=True, verbose_name="módulo Programas/Acompanhamento ativo",
        help_text="Desmarque para esconder Programas e o início de protocolo de acompanhamento dessa organização.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organização"
        verbose_name_plural = "organizações"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Usuario(AbstractUser):
    """
    Usuário do sistema. Deixar `organizacao` em branco identifica um
    administrador geral, que pode configurar todas as organizações. Qualquer
    outro usuário só enxerga e edita dados da própria organização.
    """

    class Papel(models.TextChoices):
        COMPLETO = "COMPLETO", "Acesso completo"
        COMERCIAL = "COMERCIAL", "Comercial (Agenda + CRM de leads)"

    organizacao = models.ForeignKey(
        Organizacao,
        on_delete=models.CASCADE,
        related_name="usuarios",
        blank=True,
        null=True,
        help_text="Deixe em branco apenas para administradores gerais do sistema.",
    )
    papel = models.CharField(
        max_length=20, choices=Papel.choices, default=Papel.COMPLETO,
        help_text=(
            "\"Comercial\" restringe esse usuário só à Agenda, ao CRM de leads "
            "e ao painel \"O que fazer hoje\" — o resto do sistema (ficha da "
            "paciente, prontuários, financeiro, indicadores, estoque, "
            "profissionais, programas) fica bloqueado pra ele."
        ),
    )

    comissao_fixo_mensal = models.DecimalField(
        "fixo mensal", max_digits=10, decimal_places=2, default=0, blank=True,
        help_text="Valor fixo por mês (relevante pra quem tem papel Comercial) — aparece no painel \"O que fazer hoje\" dessa pessoa.",
    )
    comissao_por_agendamento = models.DecimalField(
        "comissão por agendamento", max_digits=10, decimal_places=2, default=0, blank=True,
        help_text="Valor pago por cada consulta agendada a partir de um lead que essa pessoa trabalhou no CRM.",
    )

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.get_full_name() or self.username


class ModeloDaOrganizacao(models.Model):
    """
    Base abstrata para qualquer dado que pertence a uma organização
    (paciente, lead, consulta, etc.). Isolar por organização é o que garante
    que uma mentorada nunca veja os dados de outra.
    """

    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE)

    class Meta:
        abstract = True
