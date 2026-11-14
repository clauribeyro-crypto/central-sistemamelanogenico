import django.db.models.deletion
from django.db import migrations, models


def backfill_organizacao(apps, schema_editor):
    """
    Preenche a organização vendedora de qualquer venda já registrada antes
    desse campo existir, usando a organização principal (a única que
    oferece esse recurso de venda pra mentoradas).
    """
    VendaKitMentora = apps.get_model("core", "VendaKitMentora")
    Organizacao = apps.get_model("contas", "Organizacao")
    principal = Organizacao.objects.filter(slug="clinica-principal").first()
    if principal:
        VendaKitMentora.objects.filter(organizacao__isnull=True).update(organizacao=principal)


def reverter_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("estoque", "0006_venda_desconto"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendakitmentora",
            name="organizacao",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vendas_kit_como_fornecedora",
                to="contas.organizacao",
                help_text="Organização vendedora (quem está enviando o produto) — normalmente a sua própria.",
            ),
        ),
        migrations.AddField(
            model_name="vendakitmentora",
            name="produto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vendas_kit_mentora",
                to="estoque.produto",
                help_text=(
                    "Se o kit corresponde a um produto do seu estoque, escolha aqui — isso desconta a "
                    "quantidade do seu estoque automaticamente."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="vendakitmentora",
            name="kit_nome",
            field=models.CharField(
                blank=True,
                max_length=150,
                verbose_name="kit",
                help_text=(
                    "Nome livre, pra kits que não são um produto único do seu estoque. Deixe em branco "
                    "se escolheu um produto acima."
                ),
            ),
        ),
        migrations.RunPython(backfill_organizacao, reverter_backfill),
        migrations.AlterField(
            model_name="vendakitmentora",
            name="organizacao",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vendas_kit_como_fornecedora",
                to="contas.organizacao",
                help_text="Organização vendedora (quem está enviando o produto) — normalmente a sua própria.",
            ),
        ),
    ]
