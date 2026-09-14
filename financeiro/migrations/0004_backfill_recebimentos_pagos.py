from django.db import migrations


def preencher_recebimentos_dos_ja_pagos(apps, schema_editor):
    """
    Cria um recebimento equivalente para cada pagamento já marcado como
    Pago antes desse recurso existir — sem isso, `total_recebido` ficaria
    zerado e o próximo recálculo (disparado por qualquer novo recebimento
    de outro lançamento não teria efeito aqui, mas é uma proteção correta
    de qualquer forma) rebaixaria o status incorretamente para Pendente.
    """
    Pagamento = apps.get_model("financeiro", "Pagamento")
    Recebimento = apps.get_model("financeiro", "Recebimento")

    for pagamento in Pagamento.objects.filter(status="PAGO"):
        if pagamento.recebimentos.exists():
            continue
        Recebimento.objects.create(
            organizacao=pagamento.organizacao,
            pagamento=pagamento,
            valor=pagamento.valor,
            forma_pagamento=pagamento.forma_pagamento or "OUTRO",
            data=pagamento.data_pagamento or pagamento.data_vencimento or pagamento.criado_em.date(),
        )


def reverter(apps, schema_editor):
    pass  # não vale a pena apagar os recebimentos criados


class Migration(migrations.Migration):
    dependencies = [
        ("financeiro", "0003_alter_pagamento_data_pagamento_and_more"),
    ]

    operations = [
        migrations.RunPython(preencher_recebimentos_dos_ja_pagos, reverter),
    ]
