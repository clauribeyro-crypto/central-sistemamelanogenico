from decimal import Decimal

from django.db import migrations

VALOR_CONSULTA_INICIAL = Decimal("200.00")


def definir_valor_consulta_inicial(apps, schema_editor):
    """
    Preenche o valor padrão (R$ 200) da "Consulta inicial" para quem ainda
    não tem um valor definido — não mexe em quem já personalizou o valor.
    """
    TipoConsulta = apps.get_model("agenda", "TipoConsulta")
    TipoConsulta.objects.filter(nome="Consulta inicial", valor__isnull=True).update(
        valor=VALOR_CONSULTA_INICIAL
    )


def reverter(apps, schema_editor):
    pass  # não vale a pena voltar para "sem valor"


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0004_tipoconsulta_valor"),
    ]

    operations = [
        migrations.RunPython(definir_valor_consulta_inicial, reverter),
    ]
