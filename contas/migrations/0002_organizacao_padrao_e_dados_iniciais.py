from django.db import migrations

HORARIO_SUPORTE_PADRAO = "Segunda a sexta-feira, das 09:00 às 18:00"

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

MENSAGENS_PADRAO = {
    "CONTATO_1": (
        "Oi, {nome}! Vi que você entrou em contato buscando informações sobre "
        "o nosso acompanhamento para melasma. Quando conseguir, me responde "
        "por aqui que eu te explico direitinho. ❤️"
    ),
    "CONTATO_2": (
        "Oi, {nome}! Passando novamente por aqui porque talvez ontem você não "
        "tenha conseguido me responder. Vi que você entrou em contato buscando "
        "informações sobre o nosso acompanhamento para melasma e queria "
        "entender um pouquinho melhor o seu caso. Quando conseguir, me "
        "responde por aqui. ❤️"
    ),
    "CONTATO_3": (
        "Oi, {nome}! Separei um caso parecido com o seu para você ver os "
        "resultados do nosso acompanhamento. Dá uma olhada e me conta o que "
        "achou! ❤️"
    ),
    "CONTATO_4": (
        "Oi, {nome}! Como não tivemos retorno nas nossas últimas tentativas de "
        "contato, vou encerrar seu atendimento por aqui para não ficar te "
        "incomodando.\n\nSe em algum momento você quiser entender melhor o que "
        "pode estar acontecendo com o seu melasma e conhecer nosso "
        "acompanhamento, pode nos chamar novamente. Estaremos à disposição. ❤️"
    ),
}


def criar_organizacao_padrao(apps, schema_editor):
    """
    Cria uma organização padrão (se ainda não existir nenhuma) já com os
    dados iniciais de origens/motivos/tipos de consulta/programas, e vincula
    a ela qualquer usuário chamado "claudia" que ainda esteja sem organização
    — evita o passo manual pelo /admin/ na primeira vez que o sistema sobe
    num banco novo (ex.: Railway com Postgres recém-conectado).
    """
    Organizacao = apps.get_model("contas", "Organizacao")
    Usuario = apps.get_model("contas", "Usuario")
    Origem = apps.get_model("leads", "Origem")
    MotivoPerda = apps.get_model("leads", "MotivoPerda")
    MensagemModelo = apps.get_model("leads", "MensagemModelo")
    TipoConsulta = apps.get_model("agenda", "TipoConsulta")
    Programa = apps.get_model("programas", "Programa")

    organizacao, criada = Organizacao.objects.get_or_create(
        slug="clinica-principal", defaults={"nome": "Clínica Cláudia"}
    )

    Usuario.objects.filter(
        username__iexact="claudia", organizacao__isnull=True
    ).update(organizacao=organizacao)

    if not criada:
        # Organização já existia (de um setup manual anterior) — não duplica
        # os dados iniciais, só garante o vínculo da usuária acima.
        return

    for nome in ORIGENS_PADRAO:
        Origem.objects.get_or_create(organizacao=organizacao, nome=nome)

    for nome in MOTIVOS_PERDA_PADRAO:
        MotivoPerda.objects.get_or_create(organizacao=organizacao, nome=nome)

    for ordem, (nome, cor) in enumerate(TIPOS_CONSULTA_PADRAO):
        TipoConsulta.objects.get_or_create(
            organizacao=organizacao, nome=nome, defaults={"cor": cor, "ordem": ordem}
        )

    for dados in PROGRAMAS_PADRAO:
        Programa.objects.get_or_create(
            organizacao=organizacao, nome=dados["nome"], defaults=dados
        )

    for etapa, texto in MENSAGENS_PADRAO.items():
        MensagemModelo.objects.get_or_create(
            organizacao=organizacao, etapa=etapa, defaults={"texto": texto}
        )


def reverter(apps, schema_editor):
    # Não desfaz nada — apagar a organização e os dados dela ao reverter
    # a migração seria mais perigoso do que simplesmente deixá-los existir.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0001_initial"),
        ("leads", "0001_initial"),
        ("agenda", "0002_initial"),
        ("programas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_organizacao_padrao, reverter),
    ]
