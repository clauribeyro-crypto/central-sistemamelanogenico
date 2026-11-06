from django.db import migrations, models


def migrar_produto_para_produtos(apps, schema_editor):
    """
    Leva o produto único já vinculado (se houver) pra nova lista de
    produtos de cada venda, pra não perder o vínculo com o estoque das
    vendas já registradas antes de existir suporte a kit com mais de um
    produto.
    """
    VendaKitMentora = apps.get_model("core", "VendaKitMentora")
    for venda in VendaKitMentora.objects.filter(produto__isnull=False):
        venda.produtos.add(venda.produto_id)


def reverter_migracao(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("estoque", "0006_venda_desconto"),
        ("core", "0002_vendakitmentora_organizacao_produto"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendakitmentora",
            name="produtos",
            field=models.ManyToManyField(
                blank=True,
                related_name="vendas_kit_mentora_m2m",
                to="estoque.produto",
                help_text=(
                    "Produtos do seu estoque que fazem parte dessa venda — marque só um pra uma venda "
                    "avulsa, ou mais de um quando for um kit. A quantidade abaixo desconta de cada "
                    "produto marcado."
                ),
            ),
        ),
        migrations.RunPython(migrar_produto_para_produtos, reverter_migracao),
        migrations.RemoveField(
            model_name="vendakitmentora",
            name="produto",
        ),
        migrations.AlterField(
            model_name="vendakitmentora",
            name="kit_nome",
            field=models.CharField(
                blank=True,
                max_length=150,
                verbose_name="kit",
                help_text=(
                    "Nome livre, pra vendas que não correspondem a produto nenhum do seu estoque. Deixe "
                    "em branco se marcou produto(s) acima."
                ),
            ),
        ),
    ]
