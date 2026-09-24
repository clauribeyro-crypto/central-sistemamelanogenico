from decimal import Decimal

from django.db import migrations

MAPA_FORMA_PAGAMENTO = {"PIX": "PIX", "CARTAO": "CREDITO"}


def migrar_vendas_antigas(apps, schema_editor):
    """
    Converte cada VendaProduto (uma venda = um produto, sem controle de
    parcelamento) num Venda com um ItemVenda — e, se tinha paciente
    vinculada, também um Pagamento já marcado como Pago (com o Recebimento
    correspondente), preservando o comportamento de antes (pago na hora)
    sem perder o histórico real de vendas já lançado em produção.
    """
    VendaProduto = apps.get_model("estoque", "VendaProduto")
    Venda = apps.get_model("estoque", "Venda")
    ItemVenda = apps.get_model("estoque", "ItemVenda")
    Pagamento = apps.get_model("financeiro", "Pagamento")
    Recebimento = apps.get_model("financeiro", "Recebimento")

    for antiga in VendaProduto.objects.all():
        venda = Venda.objects.create(
            organizacao_id=antiga.organizacao_id,
            paciente_id=antiga.paciente_id,
            nome_comprador_avulso=antiga.nome_comprador_avulso,
            forma_pagamento=antiga.forma_pagamento,
            data=antiga.data,
            observacoes=antiga.observacoes,
        )
        venda.criado_em = antiga.criado_em
        venda.save(update_fields=["criado_em"])

        quantidade = antiga.quantidade or 1
        valor_unitario = (antiga.valor_total / quantidade).quantize(Decimal("0.01"))
        ItemVenda.objects.create(
            organizacao_id=antiga.organizacao_id,
            venda=venda,
            produto_id=antiga.produto_id,
            quantidade=antiga.quantidade,
            valor_unitario=valor_unitario,
        )

        if antiga.paciente_id:
            forma = MAPA_FORMA_PAGAMENTO.get(antiga.forma_pagamento, "PIX")
            pagamento = Pagamento.objects.create(
                organizacao_id=antiga.organizacao_id,
                paciente_id=antiga.paciente_id,
                venda=venda,
                valor=antiga.valor_total,
                forma_pagamento=forma,
                status="PAGO",
                data_vencimento=antiga.data,
            )
            Recebimento.objects.create(
                organizacao_id=antiga.organizacao_id,
                pagamento=pagamento,
                valor=antiga.valor_total,
                forma_pagamento=forma,
                data=antiga.data,
            )


def nao_reverte(apps, schema_editor):
    # Não dá pra desfazer com segurança (voltar juntaria o carrinho e perderia
    # o pagamento parcelado) — reversão não é suportada por esta migração.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("estoque", "0004_venda_itemvenda"),
        ("financeiro", "0006_pagamento_venda"),
    ]

    operations = [
        migrations.RunPython(migrar_vendas_antigas, nao_reverte),
        migrations.DeleteModel(name="VendaProduto"),
    ]
