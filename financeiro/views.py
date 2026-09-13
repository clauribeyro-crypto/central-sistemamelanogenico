import datetime

from django.db.models import Sum
from django.shortcuts import render

from .models import Pagamento


def relatorio(request):
    """Relatório financeiro simples, filtrável por período (mês corrente por padrão)."""
    hoje = datetime.date.today()

    data_inicio = request.GET.get("inicio")
    data_fim = request.GET.get("fim")

    if data_inicio:
        data_inicio = datetime.date.fromisoformat(data_inicio)
    else:
        data_inicio = hoje.replace(day=1)

    if data_fim:
        data_fim = datetime.date.fromisoformat(data_fim)
    else:
        data_fim = hoje

    pagamentos = Pagamento.objects.filter(
        data_vencimento__gte=data_inicio, data_vencimento__lte=data_fim
    )

    total_pago = pagamentos.filter(status=Pagamento.Status.PAGO).aggregate(
        total=Sum("valor")
    )["total"] or 0
    total_pendente = pagamentos.filter(status=Pagamento.Status.PENDENTE).aggregate(
        total=Sum("valor")
    )["total"] or 0

    por_forma_pagamento = (
        pagamentos.filter(status=Pagamento.Status.PAGO)
        .values("forma_pagamento")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    por_profissional = (
        pagamentos.filter(status=Pagamento.Status.PAGO, consulta__isnull=False)
        .values("consulta__profissional__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    contexto = {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "pagamentos": pagamentos.order_by("-data_vencimento"),
        "total_pago": total_pago,
        "total_pendente": total_pendente,
        "por_forma_pagamento": por_forma_pagamento,
        "por_profissional": por_profissional,
    }
    return render(request, "financeiro/relatorio.html", contexto)
