from django.db import models, transaction
from django.utils import timezone

from contas.models import ModeloDaOrganizacao

CAMPOS_MESCLAVEIS = [
    "cpf", "data_nascimento", "sexo", "telefone", "email",
    "endereco", "cidade", "profissao", "historico_saude", "observacoes",
]


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

    fechamento_descartado_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Preenchido quando alguém marca que, após a consulta, a paciente decidiu não continuar — tira ela da fila de fechamento sem precisar excluir nada.",
    )
    fechamento_descartado_motivo = models.CharField(max_length=255, blank=True)

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

    @classmethod
    def mesclar(cls, sobrevivente, duplicada, *, nome_final=None):
        """
        Junta os registros de `duplicada` (cadastro repetido por engano) em
        `sobrevivente` — consultas, pagamentos, leads, prontuário, anamnese
        (quando só uma das duas tem) — e apaga a duplicada. Levanta ValueError
        se as duas tiverem anamnese preenchida: nesse caso é preciso decidir
        manualmente qual anamnese manter antes de mesclar.
        """
        from agenda.models import Consulta
        from estoque.models import Recompra
        from financeiro.models import Pagamento
        from leads.models import Lead
        from programas.models import Acompanhamento
        from prontuarios.models import Anamnese, Atendimento, Documento, RegistroEvolucao

        if sobrevivente.pk == duplicada.pk:
            raise ValueError("Não dá pra mesclar uma paciente com ela mesma.")
        if sobrevivente.organizacao_id != duplicada.organizacao_id:
            raise ValueError("As duas pacientes precisam ser da mesma organização.")

        tem_anamnese_sobrevivente = Anamnese.objects.filter(paciente=sobrevivente).exists()
        tem_anamnese_duplicada = Anamnese.objects.filter(paciente=duplicada).exists()
        if tem_anamnese_sobrevivente and tem_anamnese_duplicada:
            raise ValueError(
                "As duas pacientes têm anamnese preenchida — decida qual manter "
                "antes de mesclar (edite ou apague uma delas na ficha da paciente)."
            )

        with transaction.atomic():
            Consulta.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Pagamento.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Lead.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Acompanhamento.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Atendimento.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            RegistroEvolucao.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Documento.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            Recompra.objects.filter(paciente=duplicada).update(paciente=sobrevivente)
            if tem_anamnese_duplicada and not tem_anamnese_sobrevivente:
                Anamnese.objects.filter(paciente=duplicada).update(paciente=sobrevivente)

            campos_atualizados = []
            for campo in CAMPOS_MESCLAVEIS:
                if not getattr(sobrevivente, campo) and getattr(duplicada, campo):
                    setattr(sobrevivente, campo, getattr(duplicada, campo))
                    campos_atualizados.append(campo)
            if nome_final and nome_final != sobrevivente.nome:
                sobrevivente.nome = nome_final
                campos_atualizados.append("nome")
            if campos_atualizados:
                sobrevivente.save(update_fields=campos_atualizados + ["atualizado_em"])

            duplicada.delete()

        return sobrevivente

    @property
    def precisa_fechamento(self):
        """
        Já teve consulta realizada de um tipo que costuma virar programa
        (ver TipoConsulta.conta_para_fechamento — descarta consulta de
        retorno e avulsa), não tem acompanhamento ativo e ninguém marcou
        que ela decidiu não continuar — precisa de follow-up pra fechar
        (ou não perder) a venda.
        """
        from agenda.models import Consulta
        return (
            self.fechamento_descartado_em is None
            and self.acompanhamento_atual is None
            and self.consultas.filter(
                status=Consulta.Status.REALIZADA, tipo_consulta__conta_para_fechamento=True
            ).exists()
        )
