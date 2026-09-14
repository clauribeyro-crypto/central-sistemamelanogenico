from django.db import migrations


ORIGENS_NOVAS = ["Quiz", "Consulta plano de alimentacao"]


def criar_origens(apps, schema_editor):
    """
    Garante que as origens usadas pelos novos scripts de importação
    automática (Quiz do Google Forms e o 2º formulário do Respondi) já
    existam em toda organização que já usa o módulo de leads — sem isso,
    leads importados por esses scripts cairiam na origem padrão do
    webhook em vez da origem certa, até alguém cadastrar manualmente.
    """
    Organizacao = apps.get_model("contas", "Organizacao")
    Origem = apps.get_model("leads", "Origem")

    for organizacao in Organizacao.objects.all():
        for nome in ORIGENS_NOVAS:
            Origem.objects.get_or_create(
                organizacao=organizacao,
                nome=nome,
                defaults={"ativo": True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0003_webhookimportacao"),
    ]

    operations = [
        # Sem reversão: apagar essas origens ao migrar pra trás poderia
        # remover origens que a clínica já esteja usando de verdade em
        # leads cadastrados manualmente com esse mesmo nome.
        migrations.RunPython(criar_origens, migrations.RunPython.noop),
    ]
