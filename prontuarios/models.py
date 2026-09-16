import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

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


def _campo(label, max_length=150):
    return models.CharField(label, max_length=max_length, blank=True)


def _campo_texto(label):
    return models.TextField(label, blank=True)


def _campo_satisfacao(tema):
    return models.PositiveSmallIntegerField(
        f"de 0 a 10, o quanto você está satisfeita com {tema}?",
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )


# Estrutura única (usada pelo form e pelos templates) que organiza os ~140
# campos da anamnese nas 15 seções da entrevista — cada seção some do form se
# não tiver nenhum campo preenchido ainda, e a leitura na Ficha da Paciente
# segue a mesma ordem. "satisfacao" é o nome do campo de nota 0-10 da seção,
# quando ela tiver uma (nem todas têm).
SECOES_ANAMNESE = [
    {
        "titulo": "Dados pessoais",
        "campos": ["idade", "data_nascimento", "telefone", "endereco", "profissao", "email", "peso", "altura"],
        "satisfacao": None,
    },
    {
        "titulo": "Histórico estético",
        "campos": ["tratamentos_anteriores", "tempo_desde_ultimo_tratamento", "tempo_melasma_estabilizado"],
        "satisfacao": "satisfacao_tratamentos_anteriores",
    },
    {
        "titulo": "Skincare e hábitos de pele",
        "campos": ["sabonete", "hidratante", "protetor_solar", "maquiagem", "rotina_matinal", "exposicao_solar"],
        "satisfacao": "satisfacao_pele",
    },
    {
        "titulo": "Intestino / Digestão",
        "campos": [
            "frequencia_intestinal", "esforco_evacuatorio", "fezes_endurecidas_amolecidas",
            "eliminacao_incompleta", "diarreia", "alergia_alimentar", "distensao_abdominal",
            "gases", "arrotos", "azia_refluxo", "candidiase_repeticao",
            "infeccao_urinaria_repeticao", "apetite",
        ],
        "satisfacao": "satisfacao_intestino",
    },
    {
        "titulo": "Fígado",
        "campos": [
            "acorda_enjoada", "saburra_amarelada", "desperta_madrugada", "mau_cheiro_suor_forte",
            "sede_excessiva", "gosto_metalico", "dor_de_cabeca", "fadiga",
            "multiplas_alergias", "zumbido_vertigem",
        ],
        "satisfacao": "satisfacao_figado",
    },
    {
        "titulo": "Tireoide / Energia",
        "campos": [
            "extremidades_frias", "pouco_suor_pos_treino", "marcas_dente_lingua", "unhas_fracas",
            "queda_de_cabelo", "calcanhar_rachado", "falta_de_energia", "inchaco_retencao", "pele_ressecada",
        ],
        "satisfacao": "satisfacao_energia",
    },
    {
        "titulo": "Sono",
        "campos": [
            "qualidade_sono", "horas_dormidas", "horario_dormir", "horario_acordar", "insonia",
            "despertares_noturnos", "sono_agitado_superficial", "acorda_cansada",
        ],
        "satisfacao": "satisfacao_sono",
    },
    {
        "titulo": "Saúde mental",
        "campos": [
            "ansiedade", "estresse", "irritabilidade", "mau_humor_raiva", "depressao_tristeza",
            "foco_concentracao", "memoria", "descontrole_alimentar", "vicio_em_doce",
            "baixa_libido_saude_mental", "uso_medicamentos_controlados",
        ],
        "satisfacao": "satisfacao_emocional",
    },
    {
        "titulo": "Hormônios e metabolismo",
        "campos": [
            "tpm", "fluxo_menstrual", "baixa_libido_hormonal", "sobrepeso_obesidade",
            "gordura_localizada", "celulite", "dificuldade_ganhar_peso", "massa_muscular",
            "doencas_metabolicas", "anticoncepcional", "gestacoes", "menstruacao_atual",
            "gestante", "sop",
        ],
        "satisfacao": "satisfacao_hormonal",
    },
    {
        "titulo": "Pele (condições específicas)",
        "campos": [
            "acne", "melasma", "rosacea", "psoriase", "caspa", "urticaria", "dermatite",
            "queratose_pilar", "hidradenite", "acantose_nigricans", "acrocordons", "cabelo_branco_precoce",
        ],
        "satisfacao": None,
    },
    {
        "titulo": "Alimentação",
        "campos": [
            "cafe_da_manha", "almoco", "cafe_da_tarde", "jantar", "desejo_doces_carboidratos",
            "digestao_proteinas", "preferencia_carne", "ingestao_agua",
        ],
        "satisfacao": None,
    },
    {
        "titulo": "Atividade física e hábitos",
        "campos": [
            "tipo_exercicio", "frequencia_exercicio", "tabagismo", "alcool",
            "desodorante", "shampoo", "condicionador",
        ],
        "satisfacao": None,
    },
    {
        "titulo": "Histórico médico",
        "campos": [
            "tipo_parto", "idade_menarca", "cirurgias_previas", "retirada_orgaos", "diabetes",
            "hipo_hipertireoidismo", "tratamento_medico_atual", "alergias_bijuteria_perfume_produtos",
            "antecedentes_alergicos", "marcapasso", "alteracoes_cardiacas", "hipo_hipertensao_arterial",
            "disturbio_circulatorio", "disturbio_renal", "disturbio_hormonal", "disturbio_gastrointestinal",
            "epilepsia", "alteracoes_psicologicas_psiquiatricas", "antecedentes_oncologicos",
            "endometriose", "adenomiose", "outras_doencas",
        ],
        "satisfacao": None,
    },
    {
        "titulo": "Campo aberto",
        "campos": ["outros_sintomas_doencas", "orgaos_mais_atencao"],
        "satisfacao": None,
    },
    {
        "titulo": "Foto",
        "campos": ["foto_rosto"],
        "satisfacao": None,
    },
]

# Rótulo curto de cada nota de satisfação, pro resumo visual no topo da aba.
SATISFACOES = [
    ("satisfacao_tratamentos_anteriores", "Tratamentos anteriores"),
    ("satisfacao_pele", "Pele"),
    ("satisfacao_intestino", "Intestino"),
    ("satisfacao_figado", "Disposição geral"),
    ("satisfacao_energia", "Energia"),
    ("satisfacao_sono", "Sono"),
    ("satisfacao_emocional", "Equilíbrio emocional"),
    ("satisfacao_hormonal", "Equilíbrio hormonal"),
]


class Anamnese(ModeloDaOrganizacao):
    """
    Levantamento completo de saúde da paciente, em 15 seções (ver
    `SECOES_ANAMNESE`) — preenchido pela própria paciente por um link público
    (`LinkAnamnese`) ou por um profissional na Ficha da Paciente. Um registro
    por paciente: preencher de novo atualiza o mesmo registro, não cria
    histórico (diferente da modulação, que é sempre um exame de saúde vivo,
    não uma linha do tempo de fases).
    """

    paciente = models.OneToOneField(
        Paciente, on_delete=models.PROTECT, related_name="anamnese"
    )

    # 1. Dados pessoais
    idade = models.PositiveIntegerField(null=True, blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    telefone = _campo("telefone", max_length=20)
    endereco = _campo("endereço completo", max_length=255)
    profissao = _campo("profissão")
    email = models.EmailField("e-mail", blank=True)
    peso = models.DecimalField("peso (kg)", max_digits=5, decimal_places=1, null=True, blank=True)
    altura = models.DecimalField("altura (cm)", max_digits=5, decimal_places=1, null=True, blank=True)

    # 2. Histórico estético
    tratamentos_anteriores = _campo_texto("tratamentos anteriores (quais)")
    tempo_desde_ultimo_tratamento = _campo("tempo desde o último tratamento")
    tempo_melasma_estabilizado = _campo("tempo que o melasma ficou estabilizado")
    satisfacao_tratamentos_anteriores = _campo_satisfacao(
        "os resultados dos tratamentos anteriores"
    )

    # 3. Skincare e hábitos de pele
    sabonete = _campo("sabonete")
    hidratante = _campo("hidratante")
    protetor_solar = _campo("protetor solar (marca/duração)")
    maquiagem = _campo("maquiagem")
    rotina_matinal = _campo_texto("rotina matinal")
    exposicao_solar = _campo("exposição solar")
    satisfacao_pele = _campo_satisfacao("sua pele")

    # 4. Intestino / Digestão
    frequencia_intestinal = _campo("frequência intestinal")
    esforco_evacuatorio = _campo("esforço evacuatório")
    fezes_endurecidas_amolecidas = _campo("fezes (endurecidas/amolecidas)")
    eliminacao_incompleta = _campo("eliminação incompleta")
    diarreia = _campo("diarreia")
    alergia_alimentar = _campo("alergia alimentar")
    distensao_abdominal = _campo("distensão abdominal")
    gases = _campo("gases (frequência/cheiro)")
    arrotos = _campo("arrotos")
    azia_refluxo = _campo("azia/refluxo")
    candidiase_repeticao = _campo("candidíase de repetição")
    infeccao_urinaria_repeticao = _campo("infecção urinária de repetição")
    apetite = _campo("apetite (pouco/muito)")
    satisfacao_intestino = _campo_satisfacao("o funcionamento do seu intestino")

    # 5. Fígado
    acorda_enjoada = _campo("acorda enjoada")
    saburra_amarelada = _campo("saburra amarelada")
    desperta_madrugada = _campo("desperta entre 2h e 3h da manhã")
    mau_cheiro_suor_forte = _campo("mau cheiro / suor forte")
    sede_excessiva = _campo("sede excessiva")
    gosto_metalico = _campo("gosto metálico")
    dor_de_cabeca = _campo("dor de cabeça")
    fadiga = _campo("fadiga")
    multiplas_alergias = _campo("múltiplas alergias")
    zumbido_vertigem = _campo("zumbido/vertigem")
    satisfacao_figado = _campo_satisfacao("sua disposição e bem-estar geral")

    # 6. Tireoide / Energia
    extremidades_frias = _campo("extremidades frias")
    pouco_suor_pos_treino = _campo("pouco suor pós-treino")
    marcas_dente_lingua = _campo("marcas de dente na língua")
    unhas_fracas = _campo("unhas fracas")
    queda_de_cabelo = _campo("queda de cabelo")
    calcanhar_rachado = _campo("calcanhar rachado")
    falta_de_energia = _campo("falta de energia")
    inchaco_retencao = _campo("inchaço/retenção")
    pele_ressecada = _campo("pele ressecada")
    satisfacao_energia = _campo_satisfacao("seu nível de energia")

    # 7. Sono
    qualidade_sono = _campo("qualidade do sono")
    horas_dormidas = _campo("horas dormidas", max_length=50)
    horario_dormir = _campo("horário de dormir", max_length=50)
    horario_acordar = _campo("horário de acordar", max_length=50)
    insonia = _campo("insônia")
    despertares_noturnos = _campo("despertares noturnos")
    sono_agitado_superficial = _campo("sono agitado/superficial")
    acorda_cansada = _campo("acorda cansada")
    satisfacao_sono = _campo_satisfacao("a qualidade do seu sono")

    # 8. Saúde mental
    ansiedade = _campo("ansiedade")
    estresse = _campo("estresse")
    irritabilidade = _campo("irritabilidade")
    mau_humor_raiva = _campo("mau humor/raiva")
    depressao_tristeza = _campo("depressão/tristeza")
    foco_concentracao = _campo("foco/concentração")
    memoria = _campo("memória")
    descontrole_alimentar = _campo("descontrole alimentar")
    vicio_em_doce = _campo("vício em doce")
    baixa_libido_saude_mental = _campo("baixa libido")
    uso_medicamentos_controlados = _campo("uso de medicamentos controlados")
    satisfacao_emocional = _campo_satisfacao("seu equilíbrio emocional")

    # 9. Hormônios e metabolismo
    tpm = _campo("TPM")
    fluxo_menstrual = _campo("fluxo menstrual (intensidade/coágulos)")
    baixa_libido_hormonal = _campo("baixa libido")
    sobrepeso_obesidade = _campo("sobrepeso/obesidade")
    gordura_localizada = _campo("gordura localizada")
    celulite = _campo("celulite (região)")
    dificuldade_ganhar_peso = _campo("dificuldade de ganhar peso")
    massa_muscular = _campo("massa muscular")
    doencas_metabolicas = _campo("doenças metabólicas (diabetes/hipertensão/dislipidemia)", max_length=255)
    anticoncepcional = _campo("anticoncepcional (qual)")
    gestacoes = _campo("gestações")
    menstruacao_atual = _campo("menstruação atual")
    gestante = _campo("gestante", max_length=100)
    sop = _campo("SOP (síndrome dos ovários policísticos)")
    satisfacao_hormonal = _campo_satisfacao("seu equilíbrio hormonal")

    # 10. Pele (condições específicas)
    acne = _campo("acne (região)")
    melasma = _campo("melasma")
    rosacea = _campo("rosácea")
    psoriase = _campo("psoríase")
    caspa = _campo("caspa")
    urticaria = _campo("urticária")
    dermatite = _campo("dermatite")
    queratose_pilar = _campo("queratose pilar")
    hidradenite = _campo("hidradenite")
    acantose_nigricans = _campo("acantose nigricans")
    acrocordons = _campo("acrocórdons")
    cabelo_branco_precoce = _campo("cabelo branco precoce")

    # 11. Alimentação
    cafe_da_manha = _campo("café da manhã (preferências e horário)", max_length=255)
    almoco = _campo("almoço (preferências e horário)", max_length=255)
    cafe_da_tarde = _campo("café da tarde (preferências e horário)", max_length=255)
    jantar = _campo("jantar (preferências e horário)", max_length=255)
    desejo_doces_carboidratos = _campo("desejo por doces/carboidratos")
    digestao_proteinas = _campo("digestão de proteínas")
    preferencia_carne = _campo("preferência de carne (branca/vermelha)", max_length=100)
    ingestao_agua = _campo("ingestão de água (copos/dia)", max_length=100)

    # 12. Atividade física e hábitos
    tipo_exercicio = _campo("tipo de exercício")
    frequencia_exercicio = _campo("frequência de exercício", max_length=100)
    tabagismo = _campo("tabagismo (quantidade/dia)")
    alcool = _campo("álcool (frequência/tipo)")
    desodorante = _campo("desodorante", max_length=100)
    shampoo = _campo("shampoo", max_length=100)
    condicionador = _campo("condicionador", max_length=100)

    # 13. Histórico médico
    tipo_parto = _campo("tipo de parto", max_length=100)
    idade_menarca = _campo("idade da menarca", max_length=50)
    cirurgias_previas = _campo_texto("cirurgias prévias")
    retirada_orgaos = _campo("retirada de órgãos")
    diabetes = _campo("diabetes")
    hipo_hipertireoidismo = _campo("hipo/hipertireoidismo")
    tratamento_medico_atual = _campo_texto("tratamento médico atual")
    alergias_bijuteria_perfume_produtos = _campo(
        "alergias (bijuteria/perfume/produtos)", max_length=255
    )
    antecedentes_alergicos = _campo("antecedentes alérgicos", max_length=255)
    marcapasso = _campo("marcapasso", max_length=100)
    alteracoes_cardiacas = _campo("alterações cardíacas")
    hipo_hipertensao_arterial = _campo("hipo/hipertensão arterial")
    disturbio_circulatorio = _campo("distúrbio circulatório")
    disturbio_renal = _campo("distúrbio renal")
    disturbio_hormonal = _campo("distúrbio hormonal")
    disturbio_gastrointestinal = _campo("distúrbio gastrointestinal")
    epilepsia = _campo("epilepsia (frequência)")
    alteracoes_psicologicas_psiquiatricas = _campo(
        "alterações psicológicas/psiquiátricas", max_length=255
    )
    antecedentes_oncologicos = _campo(
        "antecedentes oncológicos (câncer de mama/ovário/endométrio)", max_length=255
    )
    endometriose = _campo("endometriose", max_length=100)
    adenomiose = _campo("adenomiose", max_length=100)
    outras_doencas = _campo_texto("outras doenças")

    # 14. Campo aberto
    outros_sintomas_doencas = _campo_texto("você tem outros sintomas e/ou doenças?")
    orgaos_mais_atencao = _campo_texto("quais órgãos você sente que precisam de mais atenção?")

    # 15. Foto
    foto_rosto = models.ImageField(
        "foto do rosto", upload_to="anamnese_fotos/%Y/%m/", blank=True, null=True
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "anamnese"
        verbose_name_plural = "anamneses"

    def __str__(self):
        return f"Anamnese de {self.paciente}"

    @property
    def satisfacoes_preenchidas(self):
        """[(rótulo, nota), ...] só das notas de satisfação já respondidas, pro resumo visual."""
        return [
            (rotulo, getattr(self, campo))
            for campo, rotulo in SATISFACOES
            if getattr(self, campo) is not None
        ]

    @property
    def secoes_preenchidas(self):
        """
        [{"titulo": ..., "itens": [(rótulo, valor), ...]}, ...] só das seções
        (e campos) já respondidos — pra mostrar tudo de uma vez, sem precisar
        clicar em nada, tanto na Ficha da Paciente quanto na versão pra
        imprimir/exportar.
        """
        secoes = []
        for secao in SECOES_ANAMNESE:
            if secao["titulo"] == "Foto":
                continue
            itens = [
                (self._meta.get_field(campo).verbose_name.capitalize(), valor)
                for campo in secao["campos"]
                if (valor := getattr(self, campo))
            ]
            if itens:
                secoes.append({"titulo": secao["titulo"], "itens": itens})
        return secoes


class LinkAnamnese(models.Model):
    """
    Link público de preenchimento da anamnese — a paciente abre e responde
    sem precisar de login. Um token por link; gerar um novo não invalida os
    anteriores automaticamente, mas o profissional pode desativar um link
    manualmente (campo `ativo`) se ele for enviado por engano.
    """

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="links_anamnese")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True
    )
    preenchido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "link de anamnese"
        verbose_name_plural = "links de anamnese"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Link de anamnese de {self.paciente} ({'preenchido' if self.preenchido_em else 'pendente'})"

    @property
    def disponivel(self):
        return self.ativo and not self.preenchido_em

    def marcar_preenchido(self):
        self.preenchido_em = timezone.now()
        self.ativo = False
        self.save(update_fields=["preenchido_em", "ativo"])


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
