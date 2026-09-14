import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario

from .forms import PagamentoForm
from .models import Pagamento


def _redirecionar_com_seguranca(request, destino_padrao):
    proximo = request.POST.get("next") or request.GET.get("next")
    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect(destino_padrao)


@login_required
def relatorio(request):
    """Relatório financeiro simples, filtrável por período (mês corrente por padrão)."""
    org = organizacao_do_usuario(request)
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
        organizacao=org, data_vencimento__gte=data_inicio, data_vencimento__lte=data_fim
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


@login_required
def editar_pagamento(request, pk):
    org = organizacao_do_usuario(request)
    pagamento = get_object_or_404(Pagamento, pk=pk, organizacao=org)

    if request.method == "POST":
        form = PagamentoForm(request.POST, instance=pagamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Lançamento atualizado.")
            return _redirecionar_com_seguranca(request, reverse("financeiro:relatorio"))
    else:
        form = PagamentoForm(instance=pagamento)

    proximo = request.GET.get("next", "")
    return render(
        request, "financeiro/editar_pagamento.html",
        {"form": form, "pagamento": pagamento, "next": proximo},
    )


@login_required
@require_POST
def excluir_pagamento(request, pk):
    org = organizacao_do_usuario(request)
    pagamento = get_object_or_404(Pagamento, pk=pk, organizacao=org)
    pagamento.delete()
    messages.success(request, "Lançamento excluído.")
    return _redirecionar_com_seguranca(request, reverse("financeiro:relatorio"))
