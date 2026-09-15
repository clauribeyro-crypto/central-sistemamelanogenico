from django.conf import settings
from django.db import models

from agenda.models import Consulta
from contas.models import ModeloDaOrganizacao
from pacientes.models import Paciente
from profissionais.models import Profissional


def _storage_documento():
    """
    Exames/documentos podem ser PDF, não só imagem — usa o backend "raw" do
    Cloudinary quando configurado (variáveis CLOUDINARY_*), senão cai pro
    disco local (dev sem Cloudinary configurado).
    """
    if settings.CLOUDINARY_STORAGE.get("CLOUD_NAME"):
        from cloudinary_storage.storage import RawMediaCloudinaryStorage

        return RawMediaCloudinaryStorage()
    from django.core.files.storage import default_storage

    return default_storage


class Atendimento(ModeloDaOrganizacao):
    """Registro de prontuário de um atendimento realizado a um paciente."""

    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="atendimentos"
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="atendimentos"
    )
    consulta = models.OneToOneField(
        Consulta,
        on_delete=models.SET_NULL,
        related_name="atendimento",
        blank=True,
        null=True,
        help_text="Consulta agendada que originou este atendimento (opcional).",
    )
    data_hora = models.DateTimeField("data e hora do atendimento")

    queixa_principal = models.TextField(blank=True)
    historico_atual = models.TextField("história da doença atual", blank=True)
    exame_fisico = models.TextField(blank=True)
    diagnostico = models.TextField(blank=True)
    conduta = models.TextField(
        "conduta/procedimentos realizados", blank=True
    )
    prescricao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "atendimento"
        verbose_name_plural = "atendimentos (prontuário)"
        ordering = ["-data_hora"]
        indexes = [
            models.Index(fields=["paciente", "data_hora"]),
        ]

    def __str__(self):
        return f"Atendimento de {self.paciente} em {self.data_hora:%d/%m/%Y %H:%M}"


class Anamnese(ModeloDaOrganizacao):
    """
    Levantamento estruturado de saúde da paciente, preenchido uma vez no
    início do acompanhamento (e ajustado ao longo do tratamento, sempre por
    um administrador — ver `usuario_e_administrador`). Um registro por
    paciente, não por atendimento avulso.
    """

    paciente = models.OneToOneField(
        Paciente, on_delete=models.PROTECT, related_name="anamnese"
    )

    melasma_pele = models.TextField("melasma / pele", blank=True)
    intestino = models.TextField(blank=True)
    estomago_digestao = models.TextField("estômago / digestão", blank=True)
    figado_vesicula = models.TextField("fígado / vesícula", blank=True)
    hormonal_ciclo = models.TextField("hormonal / ciclo", blank=True)
    sono = models.TextField(blank=True)
    alimentacao = models.TextField(blank=True)
    medicamentos = models.TextField(blank=True)
    historico_saude = models.TextField("histórico de saúde", blank=True)
    sinais_sintomas = models.TextField("sinais e sintomas", blank=True)
    observacoes_profissional = models.TextField("observações do profissional", blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "anamnese"
        verbose_name_plural = "anamneses"

    def __str__(self):
        return f"Anamnese de {self.paciente}"


class Documento(ModeloDaOrganizacao):
    """Exame, laudo ou outro documento anexado à paciente (não ligado a um acompanhamento específico)."""

    class Tipo(models.TextChoices):
        EXAME = "EXAME", "Exame"
        DOCUMENTO = "DOCUMENTO", "Documento"
        OUTRO = "OUTRO", "Outro"

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="documentos")
    nome = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.EXAME)
    arquivo = models.FileField(upload_to="documentos/%Y/%m/", storage=_storage_documento)
    observacoes = models.TextField(blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "exame/documento"
        verbose_name_plural = "exames/documentos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()}) — {self.paciente}"
