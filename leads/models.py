from django.conf import settings
from django.db import models
from django.utils import timezone

from contas.models import ModeloDaOrganizacao


class Origem(ModeloDaOrganizacao):
    """De onde o lead veio (Instagram, TikTok, Indicação...). Configurável por organização."""

    nome = models.CharField(max_length=80)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "origem do lead"
        verbose_name_plural = "origens do lead"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "nome"], name="origem_unica_por_organizacao"
            ),
        ]

    def __str__(self):
        return self.nome


class MotivoPerda(ModeloDaOrganizacao):
    """Motivo de uma lead perdida. Configurável por organização."""

    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "motivo de perda"
        verbose_name_plural = "motivos de perda"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["organizacao", "nome"], name="motivo_perda_unico_por_organizacao"
            ),
        ]

    def __str__(self):
        return self.nome


class MensagemModelo(ModeloDaOrganizacao):
    """
    Modelo de mensagem de WhatsApp de uma etapa da cadência. A equipe pode
    editar o texto antes de enviar; use {nome} no texto para o nome do lead.
    """

    class Etapa(models.TextChoices):
        CONTATO_1 = "CONTATO_1", "1º contato"
        CONTATO_2 = "CONTATO_2", "2º contato"
        CONTATO_3 = "CONTATO_3", "3º contato — prova social"
        CONTATO_4 = "CONTATO_4", "4º contato — encerramento"

    etapa = models.CharField(max_length=20, choices=Etapa.choices)
    texto = models.TextField(help_text="Use {nome} para inserir o nome do lead automaticamente.")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "mensagem-modelo"
        verbose_name_plural = "mensagens-modelo"
        ordering = ["etapa"]

    def __str__(self):
        return f"{self.get_etapa_display()}"

    def render(self, lead):
        primeiro_nome = (lead.nome or "").split(" ")[0] or lead.nome
        return self.texto.format(nome=primeiro_nome)


class ProvaSocial(ModeloDaOrganizacao):
    """Biblioteca de casos de antes/depois usados no 3º contato (prova social)."""

    nome_interno = models.CharField(max_length=150)
    foto_antes = models.ImageField(upload_to="provas_sociais/antes/", blank=True)
    foto_depois = models.ImageField(upload_to="provas_sociais/depois/", blank=True)
    depoimento = models.TextField(blank=True)
    texto_sugerido = models.TextField(
        blank=True, help_text="Texto sugerido para acompanhar o envio no WhatsApp."
    )
    autorizacao_uso_imagem = models.BooleanField(
        default=False,
        verbose_name="autorização de uso de imagem registrada",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "prova social"
        verbose_name_plural = "provas sociais"
        ordering = ["nome_interno"]

    def __str__(self):
        return self.nome_interno


class Lead(ModeloDaOrganizacao):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        PAUSADO = "PAUSADO", "Pausado"
        AGENDADA = "AGENDADA", "Agendada"
        SEM_RESPOSTA = "SEM_RESPOSTA", "Sem resposta"
        PERDIDA = "PERDIDA", "Perdida"

    class Etapa(models.TextChoices):
        NOVO = "NOVO", "Novo / pendente"
        CONTATO_1 = "CONTATO_1", "1º contato"
        CONTATO_2 = "CONTATO_2", "2º contato"
        CONTATO_3 = "CONTATO_3", "3º contato — prova social"
        CONTATO_4 = "CONTATO_4", "4º contato — encerramento"
        CONCLUIDA = "CONCLUIDA", "Cadência concluída"

    nome = models.CharField("nome do paciente", max_length=150)
    whatsapp = models.CharField(max_length=20)
    telefone = models.CharField(max_length=20, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(
        "estado (UF)", max_length=2, blank=True,
        help_text="Sigla do estado, ex.: SP, RJ, MG.",
    )
    origem = models.ForeignKey(Origem, on_delete=models.PROTECT, related_name="leads")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="leads_responsavel",
        blank=True,
        null=True,
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    etapa = models.CharField(max_length=20, choices=Etapa.choices, default=Etapa.NOVO)
    tentativas_etapa_atual = models.PositiveIntegerField(
        default=0,
        help_text="Quantas tentativas de contato já foram feitas na etapa atual (reinicia a cada nova etapa).",
    )

    entrou_em = models.DateTimeField("data/hora de entrada", default=timezone.now)
    ultimo_contato_em = models.DateTimeField(blank=True, null=True)
    proxima_acao = models.CharField(max_length=255, blank=True)
    proxima_acao_em = models.DateTimeField(
        blank=True, null=True,
        help_text="Quando a próxima ação deve acontecer (usado na fila do dia).",
    )

    perdido_motivo = models.ForeignKey(
        MotivoPerda, on_delete=models.SET_NULL, blank=True, null=True, related_name="leads"
    )
    perdido_detalhe = models.TextField(
        blank=True, help_text="Preenchido quando o motivo de perda é 'Outro'."
    )

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="leads",
        help_text="Preenchido automaticamente quando a consulta é agendada.",
    )

    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "lead"
        verbose_name_plural = "leads"
        ordering = ["-entrou_em"]
        indexes = [
            models.Index(fields=["organizacao", "status"]),
            models.Index(fields=["organizacao", "etapa"]),
        ]

    def __str__(self):
        return self.nome

    @property
    def pausa_ativa(self):
        return self.pausas.filter(retomado_em__isnull=True).order_by("-criada_em").first()

    @property
    def esta_atrasado(self):
        if self.status in (self.Status.PAUSADO, self.Status.PERDIDA, self.Status.AGENDADA):
            return False
        return bool(self.proxima_acao_em and self.proxima_acao_em <= timezone.now())

    @property
    def proxima_consulta(self):
        """Consulta (ativa, não cancelada) vinculada a este lead, para exibir na aba Agendados."""
        return self.consultas.exclude(status="CANCELADA").order_by("-data_hora").first()

    def registrar_historico(self, tipo, descricao, responsavel=None):
        return self.historico.create(tipo=tipo, descricao=descricao, responsavel=responsavel)

    @classmethod
    def buscar_por_paciente(cls, organizacao, paciente):
        """
        Procura, entre os leads em cadência ativa, um que corresponda ao
        telefone ou nome dessa paciente — usado para vincular automaticamente
        o lead à consulta que acabou de ser agendada na Agenda.
        """
        filtro = models.Q(nome__iexact=paciente.nome)
        if paciente.telefone:
            filtro |= models.Q(whatsapp=paciente.telefone) | models.Q(telefone=paciente.telefone)
        return cls.objects.filter(
            organizacao=organizacao, status__in=[cls.Status.PENDENTE, cls.Status.EM_ANDAMENTO],
        ).filter(filtro).order_by("-entrou_em").first()

    def encontrar_consulta_correspondente(self):
        """
        Fallback manual (arrastar o card pra aba Agendados): procura uma
        consulta já agendada para essa paciente/lead, pelo vínculo direto
        (`paciente`) ou por telefone/nome, quando o vínculo automático não
        pegou por algum motivo.
        """
        from agenda.models import Consulta

        qs = Consulta.objects.filter(organizacao=self.organizacao).exclude(status="CANCELADA")
        if self.paciente_id:
            qs = qs.filter(paciente_id=self.paciente_id)
        else:
            filtro = models.Q(paciente__nome__iexact=self.nome)
            if self.whatsapp:
                filtro |= models.Q(paciente__telefone=self.whatsapp)
            if self.telefone:
                filtro |= models.Q(paciente__telefone=self.telefone)
            qs = qs.filter(filtro)
        return qs.order_by("-data_hora").first()

    def marcar_agendada(self, consulta=None, responsavel=None):
        """Move o lead para a aba "Agendados", vinculando a consulta encontrada, se houver."""
        self.status = self.Status.AGENDADA
        if consulta:
            self.paciente = consulta.paciente
            if consulta.lead_id != self.pk:
                consulta.lead = self
                consulta.save(update_fields=["lead"])
        self.save(update_fields=["status", "paciente", "atualizado_em"])
        descricao = "Consulta agendada"
        if consulta:
            data_hora_local = timezone.localtime(consulta.data_hora)
            descricao += f" para {data_hora_local:%d/%m/%Y %H:%M} ({consulta.tipo_consulta})"
        self.registrar_historico(HistoricoLead.Tipo.AGENDAMENTO, descricao, responsavel)

    ORDEM_ETAPAS = [
        Etapa.NOVO, Etapa.CONTATO_1, Etapa.CONTATO_2,
        Etapa.CONTATO_3, Etapa.CONTATO_4, Etapa.CONCLUIDA,
    ]

    # As etapas exibidas como colunas no board (kanban) — a cadência
    # automática ainda usa CONCLUIDA como estado terminal de "sem resposta",
    # mas essa etapa não tem coluna própria no board.
    ETAPAS_KANBAN = [Etapa.NOVO, Etapa.CONTATO_1, Etapa.CONTATO_2, Etapa.CONTATO_3, Etapa.CONTATO_4]

    def avancar_etapa(self):
        """Move a cadência para a próxima etapa e zera o contador de tentativas."""
        indice = self.ORDEM_ETAPAS.index(self.etapa)
        if indice < len(self.ORDEM_ETAPAS) - 1:
            self.etapa = self.ORDEM_ETAPAS[indice + 1]
        self.tentativas_etapa_atual = 0
        if self.etapa == self.Etapa.CONCLUIDA:
            self.status = self.Status.SEM_RESPOSTA
        self.save(update_fields=["etapa", "tentativas_etapa_atual", "status", "atualizado_em"])

    def mover_para_etapa(self, nova_etapa, responsavel=None):
        """Move o lead manualmente para outra etapa (arrastar o card no board)."""
        if nova_etapa == self.etapa:
            return
        etapa_anterior = self.get_etapa_display()
        self.etapa = nova_etapa
        self.tentativas_etapa_atual = 0
        self.status = self.Status.PENDENTE if nova_etapa == self.Etapa.NOVO else self.Status.EM_ANDAMENTO
        self.save(update_fields=["etapa", "tentativas_etapa_atual", "status", "atualizado_em"])
        self.registrar_historico(
            HistoricoLead.Tipo.STATUS,
            f"Movido manualmente de {etapa_anterior} para {self.get_etapa_display()} (arrastar no board)",
            responsavel,
        )

    def marcar_respondido(self, responsavel=None):
        """
        Botão rápido do card no board: avança a cadência por resposta da lead,
        sem precisar abrir a tela de detalhe. Para na última etapa da cadência
        (4º contato) — não empurra sozinho para "cadência concluída".
        """
        indice = self.ORDEM_ETAPAS.index(self.etapa)
        indice_maximo = self.ORDEM_ETAPAS.index(self.Etapa.CONTATO_4)
        etapa_anterior = self.get_etapa_display()
        if indice < indice_maximo:
            self.etapa = self.ORDEM_ETAPAS[indice + 1]
        self.status = self.Status.EM_ANDAMENTO
        self.tentativas_etapa_atual = 0
        self.ultimo_contato_em = timezone.now()
        self.save(update_fields=[
            "etapa", "tentativas_etapa_atual", "status", "ultimo_contato_em", "atualizado_em",
        ])
        self.registrar_historico(
            HistoricoLead.Tipo.RESPOSTA,
            f"Marcado como respondido — avançou de {etapa_anterior} para {self.get_etapa_display()}",
            responsavel,
        )


class HistoricoLead(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada do lead"
        LIGACAO = "LIGACAO", "Ligação"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        RESPOSTA = "RESPOSTA", "Resposta do lead"
        STATUS = "STATUS", "Mudança de status/etapa"
        PAUSA = "PAUSA", "Cadência pausada"
        RETOMADA = "RETOMADA", "Cadência retomada"
        AGENDAMENTO = "AGENDAMENTO", "Consulta agendada"
        PERDA = "PERDA", "Lead perdida"
        NOTA = "NOTA", "Observação"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="historico")
    data_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    descricao = models.CharField(max_length=500)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        verbose_name = "histórico do lead"
        verbose_name_plural = "histórico dos leads"
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.lead} — {self.descricao}"


class PausaLead(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="pausas")
    criada_em = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=255)
    data_retomada_prevista = models.DateField()
    observacao = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )
    retomado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "pausa de cadência"
        verbose_name_plural = "pausas de cadência"
        ordering = ["-criada_em"]

    def __str__(self):
        return f"Pausa de {self.lead} até {self.data_retomada_prevista:%d/%m/%Y}"
