from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from contas.models import Organizacao

ORIGENS_PADRAO = ["Instagram", "TikTok", "Indicação", "Outros"]

MOTIVOS_PERDA_PADRAO = [
    "Valor", "Sem interesse", "Não é o momento", "Não conseguiu agenda",
    "Procurava outro serviço", "Não respondeu depois de conversar", "Outro",
]

TIPOS_CONSULTA_PADRAO = [
    ("Consulta inicial", "#8B5FBF"),
    ("Consulta de diagnóstico", "#C2679A"),
    ("Retorno", "#4C9A7C"),
    ("Reavaliação", "#D1994A"),
    ("Consulta final", "#C2694A"),
    ("Reunião interna", "#8A8594"),
]

HORARIO_SUPORTE_PADRAO = "Segunda a sexta-feira, das 09:00 às 18:00"

PROGRAMAS_PADRAO = [
    dict(
        nome="Programa de 3 meses", duracao_meses=3, valor=5000, valor_a_vista=4500,
        parcelamento_max=12, qtd_consultas=2, qtd_modulacoes=1, qtd_kits=1,
        produtos_incluidos="1 kit: 1 produto para o dia + 1 produto para a noite",
        horario_suporte=HORARIO_SUPORTE_PADRAO,
    ),
    dict(
        nome="Programa de 6 meses", duracao_meses=6, valor=7000, valor_a_vista=6500,
        parcelamento_max=12, qtd_consultas=3, qtd_modulacoes=1, qtd_kits=2,
        produtos_incluidos="2 kits: 2 produtos para o dia + 2 produtos para a noite",
        horario_suporte=HORARIO_SUPORTE_PADRAO,
    ),
    dict(
        nome="Programa de 9 meses", duracao_meses=9, valor=12000, valor_a_vista=11000,
        parcelamento_max=12, qtd_consultas=4, qtd_modulacoes=2, qtd_kits=4,
        produtos_incluidos="4 kits: 4 produtos para o dia + 4 produtos para a noite",
        horario_suporte=HORARIO_SUPORTE_PADRAO,
    ),
]


class Command(BaseCommand):
    help = (
        "Cria a organização (clínica) inicial e vincula automaticamente o "
        "primeiro superusuário que ainda não tem organização."
    )

    def add_arguments(self, parser):
        parser.add_argument("nome", type=str, help="Nome da clínica/organização")

    def handle(self, *args, **options):
        nome = options["nome"].strip()

        slug_base = slugify(nome) or "clinica"
        slug = slug_base
        contador = 1
        while Organizacao.objects.filter(slug=slug).exists():
            contador += 1
            slug = f"{slug_base}-{contador}"

        organizacao = Organizacao.objects.create(nome=nome, slug=slug)
        self.stdout.write(self.style.SUCCESS(f"Organização '{organizacao.nome}' criada."))

        self._popular_dados_iniciais(organizacao)

        Usuario = get_user_model()
        usuario = (
            Usuario.objects.filter(is_superuser=True, organizacao__isnull=True)
            .order_by("id")
            .first()
        )
        if usuario:
            usuario.organizacao = organizacao
            usuario.save(update_fields=["organizacao"])
            self.stdout.write(self.style.SUCCESS(
                f"Usuário '{usuario.username}' vinculado à organização '{organizacao.nome}'."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "Nenhum superusuário sem organização encontrado. Vincule manualmente "
                "pelo /admin/ em Contas > Usuários."
            ))

    def _popular_dados_iniciais(self, organizacao):
        from agenda.models import TipoConsulta
        from leads.models import MensagemModelo, MotivoPerda, Origem
        from leads.views import MENSAGENS_PADRAO
        from programas.models import Programa

        for nome in ORIGENS_PADRAO:
            Origem.objects.create(organizacao=organizacao, nome=nome)

        for nome in MOTIVOS_PERDA_PADRAO:
            MotivoPerda.objects.create(organizacao=organizacao, nome=nome)

        for ordem, (nome, cor) in enumerate(TIPOS_CONSULTA_PADRAO):
            TipoConsulta.objects.create(organizacao=organizacao, nome=nome, cor=cor, ordem=ordem)

        for etapa, texto in MENSAGENS_PADRAO.items():
            MensagemModelo.objects.create(organizacao=organizacao, etapa=etapa, texto=texto)

        for dados in PROGRAMAS_PADRAO:
            Programa.objects.create(organizacao=organizacao, **dados)

        self.stdout.write(self.style.SUCCESS(
            "Origens, motivos de perda, tipos de consulta, mensagens-modelo e programas de "
            "acompanhamento (3/6/9 meses) padrão criados (edite tudo em /admin/ quando quiser)."
        ))
