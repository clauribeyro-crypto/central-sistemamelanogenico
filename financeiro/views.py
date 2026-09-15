import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario

from .forms import PagamentoForm, RecebimentoForm
from .models import Pagamento, Recebimento


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

    pagamentos_vencendo_no_periodo = Pagamento.objects.filter(
        organizacao=org, data_vencimento__gte=data_inicio, data_vencimento__lte=data_fim
    )

    # "Recebido" é sempre baseado na data em que o dinheiro de fato entrou
    # (a data do recebimento), não na data de vencimento do lançamento —
    # senão uma entrada paga adiantado pra uma consulta futura (vencimento
    # fora do período) ficaria de fora do total recebido, mesmo já tendo
    # sido recebida dentro do período selecionado.
    recebimentos_no_periodo = Recebimento.objects.filter(
        organizacao=org, data__gte=data_inicio, data__lte=data_fim,
    )
    total_pago = recebimentos_no_periodo.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    pagamentos_em_aberto = pagamentos_vencendo_no_periodo.filter(
        status__in=[Pagamento.Status.PENDENTE, Pagamento.Status.PARCIAL]
    )
    total_pendente = sum((p.saldo_pendente for p in pagamentos_em_aberto), Decimal("0.00"))

    por_forma_pagamento = (
        recebimentos_no_periodo
        .values("forma_pagamento")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    por_profissional = (
        recebimentos_no_periodo.filter(pagamento__consulta__isnull=False)
        .values("pagamento__consulta__profissional__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    # A tabela mostra tanto quem vence no período quanto quem recebeu algo
    # no período (mesmo com vencimento fora dele) — assim todo valor que
    # entra nos totais acima tem uma linha clicável pra conferir de onde veio.
    ids_com_recebimento_no_periodo = recebimentos_no_periodo.values_list("pagamento_id", flat=True)
    pagamentos = (
        Pagamento.objects.filter(organizacao=org)
        .filter(Q(pk__in=pagamentos_vencendo_no_periodo) | Q(pk__in=ids_com_recebimento_no_periodo))
        .distinct()
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
    proximo = request.GET.get("next") or request.POST.get("next") or ""
    url_desta_pagina = f"{reverse('financeiro:editar_pagamento', args=[pagamento.pk])}?next={proximo}"

    form = None
    recebimento_form = None

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "salvar_pagamento":
            form = PagamentoForm(request.POST, instance=pagamento)
            if form.is_valid():
                form.save()
                messages.success(request, "Lançamento atualizado.")
                return _redirecionar_com_seguranca(request, reverse("financeiro:relatorio"))

        elif acao == "adicionar_recebimento":
            recebimento_form = RecebimentoForm(request.POST, pagamento=pagamento)
            if recebimento_form.is_valid():
                recebimento = recebimento_form.save(commit=False)
                recebimento.organizacao = org
                recebimento.pagamento = pagamento
                recebimento.save()
                messages.success(request, "Recebimento registrado.")
                return redirect(url_desta_pagina)

        elif acao == "excluir_recebimento":
            recebimento = get_object_or_404(
                Recebimento, pk=request.POST.get("recebimento_id"), pagamento=pagamento, organizacao=org
            )
            recebimento.delete()
            messages.success(request, "Recebimento excluído.")
            return redirect(url_desta_pagina)

    if form is None:
        form = PagamentoForm(instance=pagamento)
    if recebimento_form is None:
        recebimento_form = RecebimentoForm(pagamento=pagamento)

    contexto = {
        "form": form,
        "pagamento": pagamento,
        "recebimento_form": recebimento_form,
        "recebimentos": pagamento.recebimentos.all(),
        "next": proximo,
    }
    return render(request, "financeiro/editar_pagamento.html", contexto)


@login_required
@require_POST
def excluir_pagamento(request, pk):
    org = organizacao_do_usuario(request)
    pagamento = get_object_or_404(Pagamento, pk=pk, organizacao=org)
    pagamento.delete()
    messages.success(request, "Lançamento excluído.")
    return _redirecionar_com_seguranca(request, reverse("financeiro:relatorio"))
