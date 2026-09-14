from django.db import migrations

# Cor "de fábrica" do campo TipoConsulta.cor (o valor que qualquer tipo de
# consulta criado pelo /admin/ sem trocar a cor acaba ficando) — é o que
# fazia a agenda parecer "tudo na mesma cor".
COR_PADRAO_DO_CAMPO = "#7C3AED"

NOVAS_CORES_POR_NOME = {
    "Consulta inicial": "#8B5FBF",
    "Consulta de diagnóstico": "#C2679A",
    "Retorno": "#4C9A7C",
    "Reavaliação": "#D1994A",
    "Consulta final": "#C2694A",
    "Reunião interna": "#8A8594",
}


def corrigir_cores(apps, schema_editor):
    TipoConsulta = apps.get_model("agenda", "TipoConsulta")
    for nome, cor in NOVAS_CORES_POR_NOME.items():
        # Só corrige quem ainda está na cor "de fábrica" — se alguém já
        # escolheu outra cor de propósito, não mexe.
        TipoConsulta.objects.filter(nome=nome, cor=COR_PADRAO_DO_CAMPO).update(cor=cor)


def reverter(apps, schema_editor):
    pass  # não vale a pena voltar para a cor de fábrica


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(corrigir_cores, reverter),
    ]
