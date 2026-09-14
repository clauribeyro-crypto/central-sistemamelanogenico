import datetime

from django.db import models
from django.utils import timezone

from contas.models import ModeloDaOrganizacao


class Programa(ModeloDaOrganizacao):
    """
    Modelo configurável de protocolo de acompanhamento (ex.: 3, 6 ou 9 meses).
    Nada aqui é fixo no código — a equipe cria/edita programas pelo /admin/.
    """

    nome = models.CharField(max_length=100)
    duracao_meses = models.PositiveIntegerField()

    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_a_vista = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    parcelamento_max = models.PositiveIntegerField(default=12)

    qtd_consultas = models.PositiveIntegerField(default=1)
    qtd_modulacoes = models.PositiveIntegerField(default=1)
    qtd_kits = models.PositiveIntegerField(default=1)

    produtos_incluidos = models.CharField(
        max_length=255, blank=True,
        help_text="Ex.: 1 produto para o dia + 1 produto para a noite por kit.",
    )
    horario_suporte = models.CharField(
        max_length=150, blank=True,
        help_text="Ex.: Segunda a sexta-feira, das 09:00 às 18:00.",
    )

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "programa de acompanhamento"
        verbose_name_plural = "programas de acompanhamento"
        ordering = ["duracao_meses"]

    def __str__(self):
        return self.nome


class Acompanhamento(ModeloDaOrganizacao):
    """Um programa efetivamente contratado por uma paciente."""

    class Status(models.TextChoices):
        EM_ACOMPANHAMENTO = "EM_ACOMPANHAMENTO", "Em acompanhamento"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        AGUARDANDO_DECISAO = "AGUARDANDO_DECISAO", "Aguardando decisão"
        RENOVADO = "RENOVADO", "Renovado"
        MIGRADO = "MIGRADO", "Migrado para outro programa"
        FINALIZADO = "FINALIZADO", "Finalizado"
        CANCELADO = "CANCELADO", "Cancelado"

    STATUS_ATIVOS = (Status.EM_ACOMPANHAMENTO, Status.MANUTENCAO, Status.AGUARDANDO_DECISAO)

    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.CASCADE, related_name="acompanhamentos"
    )
    programa = models.ForeignKey(Programa, on_delete=models.PROTECT, related_name="acompanhamentos")

    data_inicio = models.DateField(default=timezone.localdate)
    data_termino_prevista = models.DateField()
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.EM_ACOMPANHAMENTO)

    valor_contratado = models.DecimalField(max_digits=10, decimal_places=2)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pagamento = models.CharField(max_length=100, blank=True)

    modulacao_concluida = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "acompanhamento"
        verbose_name_plural = "acompanhamentos"
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"{self.paciente} — {self.programa} ({self.get_status_display()})"

    @property
    def dias_restantes(self):
        return (self.data_termino_prevista - timezone.localdate()).days

    @classmethod
    def iniciar(cls, *, paciente, programa, data_inicio, valor_contratado=None,
                desconto=0, forma_pagamento="", observacoes=""):
        """Cria o acompanhamento e já gera o checklist de consultas e kits previstos."""
        data_termino = data_inicio + datetime.timedelta(days=30 * programa.duracao_meses)
        acompanhamento = cls.objects.create(
            organizacao=programa.organizacao,
            paciente=paciente,
            programa=programa,
            data_inicio=data_inicio,
            data_termino_prevista=data_termino,
            valor_contratado=valor_contratado if valor_contratado is not None else programa.valor,
            desconto=desconto,
            forma_pagamento=forma_pagamento,
            observacoes=observacoes,
        )
        for numero in range(1, programa.qtd_consultas + 1):
            ConsultaPrevista.objects.create(acompanhamento=acompanhamento, numero=numero)
        for numero in range(1, programa.qtd_kits + 1):
            KitPrevisto.objects.create(acompanhamento=acompanhamento, numero=numero)

        # Gera automaticamente a receita prevista (pendente) do plano fechado.
        from financeiro.models import Pagamento

        Pagamento.objects.create(
            organizacao=acompanhamento.organizacao,
            paciente=paciente,
            acompanhamento=acompanhamento,
            valor=acompanhamento.valor_contratado - acompanhamento.desconto,
            forma_pagamento=forma_pagamento,
            status=Pagamento.Status.PENDENTE,
            data_vencimento=data_inicio,
        )

        return acompanhamento

    def jornada(self):
        """Monta a lista de etapas (diagnóstico → modulações → consultas/kits intercalados → finalização)."""
        etapas = [{"nome": "Consulta de diagnóstico", "concluida": True}]

        for i in range(self.programa.qtd_modulacoes):
            nome = "Modulação" if self.programa.qtd_modulacoes == 1 else f"Modulação {i + 1}"
            etapas.append({"nome": nome, "concluida": self.modulacao_concluida})

        consultas = list(self.consultas_previstas.order_by("numero"))
        kits = list(self.kits_previstos.order_by("numero"))
        i = j = 0
        while i < len(consultas) or j < len(kits):
            if i < len(consultas):
                c = consultas[i]
                etapas.append({"nome": f"Consulta {c.numero}", "concluida": c.status == c.Status.REALIZADA})
                i += 1
            if j < len(kits):
                k = kits[j]
                etapas.append({"nome": f"Kit {k.numero}", "concluida": k.status == k.Status.ENVIADO})
                j += 1

        etapas.append({
            "nome": "Finalização",
            "concluida": self.status in (self.Status.FINALIZADO, self.Status.RENOVADO, self.Status.MIGRADO),
        })

        atual_marcada = False
        for etapa in etapas:
            if not etapa["concluida"] and not atual_marcada:
                etapa["atual"] = True
                atual_marcada = True
            else:
                etapa["atual"] = False
        return etapas

    def alertas(self):
        alertas = []
        primeira_consulta_pendente = self.consultas_previstas.filter(
            status=ConsultaPrevista.Status.PENDENTE_AGENDAMENTO
        ).order_by("numero").first()
        if primeira_consulta_pendente:
            alertas.append(f"Consulta {primeira_consulta_pendente.numero} precisa ser agendada.")

        consultas_realizadas = self.consultas_previstas.filter(
            status=ConsultaPrevista.Status.REALIZADA
        ).count()
        for kit in self.kits_previstos.filter(status=KitPrevisto.Status.PENDENTE).order_by("numero"):
            if kit.numero <= consultas_realizadas:
                alertas.append(f"Kit {kit.numero} precisa ser enviado.")

        if self.status in self.STATUS_ATIVOS:
            dias = self.dias_restantes
            if 0 <= dias <= 30:
                alertas.append(f"Faltam {dias} dias para o término do acompanhamento.")
            elif dias < 0:
                alertas.append("O acompanhamento já passou da data prevista de término.")
        return alertas


class ConsultaPrevista(models.Model):
    class Status(models.TextChoices):
        PENDENTE_AGENDAMENTO = "PENDENTE_AGENDAMENTO", "Pendente de agendamento"
        AGENDADA = "AGENDADA", "Agendada"
        REALIZADA = "REALIZADA", "Realizada"
        REAGENDADA = "REAGENDADA", "Reagendada"
        CANCELADA = "CANCELADA", "Cancelada"

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="consultas_previstas"
    )
    numero = models.PositiveIntegerField()
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDENTE_AGENDAMENTO)
    consulta = models.ForeignKey(
        "agenda.Consulta", on_delete=models.SET_NULL, blank=True, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "consulta prevista"
        verbose_name_plural = "consultas previstas"
        ordering = ["numero"]
        unique_together = ("acompanhamento", "numero")

    def __str__(self):
        return f"Consulta {self.numero} de {self.acompanhamento}"


class KitPrevisto(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        ENVIADO = "ENVIADO", "Enviado"

    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="kits_previstos"
    )
    numero = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    data_envio = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "kit previsto"
        verbose_name_plural = "kits previstos"
        ordering = ["numero"]
        unique_together = ("acompanhamento", "numero")

    def __str__(self):
        return f"Kit {self.numero} de {self.acompanhamento}"


class CustoAcompanhamento(models.Model):
    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE, related_name="custos"
    )
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name = "custo do acompanhamento"
        verbose_name_plural = "custos do acompanhamento"
        ordering = ["-data"]

    def __str__(self):
        return f"{self.descricao} — R$ {self.valor}"
