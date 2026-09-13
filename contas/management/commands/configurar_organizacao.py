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
    ("Consulta inicial", "#7C3AED"),
    ("Consulta de diagnóstico", "#2563EB"),
    ("Retorno", "#16A34A"),
    ("Reavaliação", "#CA8A04"),
    ("Consulta final", "#EA580C"),
    ("Reunião interna", "#6B7280"),
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

        for nome in ORIGENS_PADRAO:
            Origem.objects.create(organizacao=organizacao, nome=nome)

        for nome in MOTIVOS_PERDA_PADRAO:
            MotivoPerda.objects.create(organizacao=organizacao, nome=nome)

        for ordem, (nome, cor) in enumerate(TIPOS_CONSULTA_PADRAO):
            TipoConsulta.objects.create(organizacao=organizacao, nome=nome, cor=cor, ordem=ordem)

        for etapa, texto in MENSAGENS_PADRAO.items():
            MensagemModelo.objects.create(organizacao=organizacao, etapa=etapa, texto=texto)

        self.stdout.write(self.style.SUCCESS(
            "Origens, motivos de perda, tipos de consulta e mensagens-modelo padrão criados "
            "(edite tudo em /admin/ quando quiser)."
        ))
