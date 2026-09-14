from django.db import migrations


def preencher_valor_das_consultas_existentes(apps, schema_editor):
    """
    Preenche `Consulta.valor` com o valor padrão do tipo de consulta para
    consultas já existentes (criadas antes desse campo existir) — mantém a
    agenda e o Financeiro consistentes sem duplicar nenhum pagamento já
    gerado anteriormente (esta migração só ajusta o campo, não dispara sinais).
    """
    TipoConsulta = apps.get_model("agenda", "TipoConsulta")
    Consulta = apps.get_model("agenda", "Consulta")
    for tipo in TipoConsulta.objects.filter(valor__isnull=False):
        Consulta.objects.filter(tipo_consulta=tipo, valor__isnull=True).update(valor=tipo.valor)


def reverter(apps, schema_editor):
    pass  # não vale a pena voltar para "sem valor"


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0006_consulta_valor"),
    ]

    operations = [
        migrations.RunPython(preencher_valor_das_consultas_existentes, reverter),
    ]
