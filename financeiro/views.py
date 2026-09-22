import calendar
import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from agenda.models import Consulta
from contas.utils import modulo_ativo_obrigatorio, organizacao_do_usuario, usuario_e_administrador
from programas.models import Acompanhamento

from .forms import BancoForm, CategoriaFinanceiraForm, LancamentoForm, PagamentoForm, RecebimentoForm
from .models import Banco, CategoriaFinanceira, Lancamento, Pagamento, Recebimento

MESES = [
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
]


def _totais_periodo(org, data_inicio, data_fim, status=Lancamento.Status.REALIZADO):
    """
    Soma receitas/despesas no período: lançamentos manuais pelo grupo da
    categoria, mais os recebimentos das pacientes (só entram como receita
    realizada — a cobrança em aberto de uma paciente é "previsto" e é
    tratada à parte, junto do saldo pendente dos pagamentos).
    """
    lancamentos = Lancamento.objects.filter(
        organizacao=org, status=status, data__gte=data_inicio, data__lte=data_fim
    )
    receitas = lancamentos.filter(
        categoria__grupo__in=CategoriaFinanceira.GRUPOS_RECEITA
    ).aggregate(t=Sum("valor"))["t"] or Decimal("0.00")
    despesas = lancamentos.exclude(
        categoria__grupo__in=CategoriaFinanceira.GRUPOS_RECEITA
    ).aggregate(t=Sum("valor"))["t"] or Decimal("0.00")

    if status == Lancamento.Status.REALIZADO:
        receitas += Recebimento.objects.filter(
            organizacao=org, data__gte=data_inicio, data__lte=data_fim
        ).aggregate(t=Sum("valor"))["t"] or Decimal("0.00")

    return {"receitas": receitas, "despesas": despesas, "resultado": receitas - despesas}


def _saldo_ate(org, data_limite):
    """Saldo em caixa acumulado (realizado) até uma data, a partir do saldo inicial da organização."""
    totais = _totais_periodo(org, datetime.date.min, data_limite)
    return org.saldo_inicial_financeiro + totais["resultado"]


def _redirecionar_com_seguranca(request, destino_padrao):
    proximo = request.POST.get("next") or request.GET.get("next")
    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect(destino_padrao)


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
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
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def relatorio_fechamentos(request):
    """
    Relatório do mês pra imprimir: programas/tratamentos fechados (contratos
    assinados no período) de um lado, consultas cobradas do outro — são
    duas fontes de faturamento bem diferentes e a Cláudia quer ver cada uma
    separada, não misturada num total só de "pagamentos".
    """
    org = organizacao_do_usuario(request)
    hoje = datetime.date.today()

    try:
        ano = int(request.GET.get("ano", hoje.year))
    except ValueError:
        ano = hoje.year
    try:
        mes = int(request.GET.get("mes", hoje.month))
    except ValueError:
        mes = hoje.month
    if mes < 1 or mes > 12:
        mes = hoje.month

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    data_inicio = datetime.date(ano, mes, 1)
    data_fim = datetime.date(ano, mes, ultimo_dia)

    tratamentos = list(
        Acompanhamento.objects.filter(
            organizacao=org, data_inicio__gte=data_inicio, data_inicio__lte=data_fim,
        ).select_related("paciente", "programa").order_by("data_inicio")
    )
    for t in tratamentos:
        t.valor_liquido = t.valor_contratado - t.desconto
        pagamento = t.pagamentos.first()
        t.total_recebido = pagamento.total_recebido if pagamento else Decimal("0.00")
    total_tratamentos = sum((t.valor_liquido for t in tratamentos), Decimal("0.00"))
    total_recebido_tratamentos = sum((t.total_recebido for t in tratamentos), Decimal("0.00"))

    consultas = list(
        Consulta.objects.filter(
            organizacao=org, data_hora__date__gte=data_inicio, data_hora__date__lte=data_fim, valor__gt=0,
        ).exclude(status=Consulta.Status.CANCELADA)
        .select_related("paciente", "tipo_consulta", "profissional").order_by("data_hora")
    )
    for c in consultas:
        pagamento = c.pagamentos.first()
        c.total_recebido = pagamento.total_recebido if pagamento else Decimal("0.00")
    total_consultas = sum((c.valor for c in consultas), Decimal("0.00"))
    total_recebido_consultas = sum((c.total_recebido for c in consultas), Decimal("0.00"))

    contexto = {
        "ano": ano,
        "mes": mes,
        "mes_nome": dict(MESES)[mes],
        "meses": MESES,
        "anos": range(hoje.year - 3, hoje.year + 2),
        "tratamentos": tratamentos,
        "total_tratamentos": total_tratamentos,
        "total_recebido_tratamentos": total_recebido_tratamentos,
        "consultas": consultas,
        "total_consultas": total_consultas,
        "total_recebido_consultas": total_recebido_consultas,
        "total_geral": total_tratamentos + total_consultas,
        "total_recebido_geral": total_recebido_tratamentos + total_recebido_consultas,
    }
    return render(request, "financeiro/relatorio_fechamentos.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
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
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
@require_POST
def excluir_pagamento(request, pk):
    org = organizacao_do_usuario(request)
    pagamento = get_object_or_404(Pagamento, pk=pk, organizacao=org)
    pagamento.delete()
    messages.success(request, "Lançamento excluído.")
    return _redirecionar_com_seguranca(request, reverse("financeiro:relatorio"))


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def painel(request):
    """Controle Financeiro: painel com abas Geral (dashboard), Lançamentos e Resumo Mensal."""
    org = organizacao_do_usuario(request)
    hoje = datetime.date.today()
    aba = request.GET.get("aba", "geral")

    try:
        ano = int(request.GET.get("ano", hoje.year))
    except ValueError:
        ano = hoje.year
    try:
        mes = int(request.GET.get("mes", hoje.month))
    except ValueError:
        mes = hoje.month
    if mes < 1 or mes > 12:
        mes = hoje.month

    contexto = {
        "aba": aba,
        "ano": ano,
        "mes": mes,
        "meses": MESES,
        "anos": range(hoje.year - 3, hoje.year + 2),
        "pode_editar": usuario_e_administrador(request),
    }

    if aba == "lancamentos":
        todos_periodos = request.GET.get("todos_periodos") == "1"
        lancamentos = Lancamento.objects.filter(organizacao=org)
        if not todos_periodos:
            lancamentos = lancamentos.filter(data__year=ano, data__month=mes)

        banco_id = request.GET.get("banco")
        if banco_id:
            lancamentos = lancamentos.filter(banco_id=banco_id)

        status = request.GET.get("status")
        if status in Lancamento.Status.values:
            lancamentos = lancamentos.filter(status=status)

        grupo = request.GET.get("grupo")
        if grupo in CategoriaFinanceira.Grupo.values:
            lancamentos = lancamentos.filter(categoria__grupo=grupo)

        if todos_periodos:
            # "ver de todos os períodos" existe pra caçar lançamentos previstos
            # esquecidos em qualquer data — não faz sentido somar um total de
            # receitas/despesas "do período" quando não há período nenhum.
            total_receitas = total_despesas = None
        else:
            totais = _totais_periodo(
                org, datetime.date(ano, mes, 1), datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])
            )
            total_receitas = totais["receitas"]
            total_despesas = totais["despesas"]

        contexto.update({
            "lancamentos": lancamentos.select_related("categoria", "banco"),
            "bancos": Banco.objects.filter(organizacao=org, ativo=True),
            "grupos": CategoriaFinanceira.Grupo.choices,
            "banco_selecionado": banco_id or "",
            "status_selecionado": status or "",
            "grupo_selecionado": grupo or "",
            "todos_periodos": todos_periodos,
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
        })

    elif aba == "resumo_mensal":
        saldo = _saldo_ate(org, datetime.date(ano, 1, 1) - datetime.timedelta(days=1))
        linhas = []
        for numero_mes, nome_mes in MESES:
            ultimo_dia = calendar.monthrange(ano, numero_mes)[1]
            totais = _totais_periodo(org, datetime.date(ano, numero_mes, 1), datetime.date(ano, numero_mes, ultimo_dia))
            saldo_inicial = saldo
            saldo = saldo_inicial + totais["resultado"]
            linhas.append({
                "mes": nome_mes,
                "saldo_inicial": saldo_inicial,
                "entradas": totais["receitas"],
                "saidas": totais["despesas"],
                "saldo_final": saldo,
            })
        contexto["linhas"] = linhas

    else:  # geral (dashboard)
        totais_ano = _totais_periodo(org, datetime.date(ano, 1, 1), datetime.date(ano, 12, 31))
        ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
        totais_mes = _totais_periodo(org, datetime.date(ano, mes, 1), datetime.date(ano, mes, ultimo_dia_mes))

        saldo_hoje = _saldo_ate(org, hoje)

        # Só a pendência real de paciente (dinheiro que ainda vai entrar) —
        # sem misturar com "lançamentos previstos" do Financeiro geral, que
        # é um conceito à parte e só confunde essa conta.
        saldo_pendente_pacientes = sum(
            (p.saldo_pendente for p in Pagamento.objects.filter(organizacao=org).exclude(status=Pagamento.Status.CANCELADO)),
            Decimal("0.00"),
        )
        saldo_futuro_previsto = saldo_hoje + saldo_pendente_pacientes

        grafico = []
        maior_valor = Decimal("0.01")
        for numero_mes, nome_mes in MESES:
            ultimo_dia = calendar.monthrange(ano, numero_mes)[1]
            totais_do_mes = _totais_periodo(org, datetime.date(ano, numero_mes, 1), datetime.date(ano, numero_mes, ultimo_dia))
            grafico.append({"mes": nome_mes[:3], "receitas": totais_do_mes["receitas"], "despesas": totais_do_mes["despesas"]})
            maior_valor = max(maior_valor, totais_do_mes["receitas"], totais_do_mes["despesas"])

        for item in grafico:
            item["altura_receitas"] = int(item["receitas"] / maior_valor * 100)
            item["altura_despesas"] = int(item["despesas"] / maior_valor * 100)

        contexto.update({
            "receitas_ano": totais_ano["receitas"],
            "despesas_ano": totais_ano["despesas"],
            "resultado_ano": totais_ano["resultado"],
            "receitas_mes": totais_mes["receitas"],
            "despesas_mes": totais_mes["despesas"],
            "resultado_mes": totais_mes["resultado"],
            "saldo_hoje": saldo_hoje,
            "saldo_pendente_pacientes": saldo_pendente_pacientes,
            "saldo_futuro_previsto": saldo_futuro_previsto,
            "grafico": grafico,
            "saldo_inicial_financeiro": org.saldo_inicial_financeiro,
        })

    return render(request, "financeiro/painel.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
@require_POST
def salvar_saldo_inicial(request):
    org = organizacao_do_usuario(request)
    if not usuario_e_administrador(request):
        messages.error(request, "Só administradores podem alterar o saldo inicial.")
        return redirect(f"{reverse('financeiro:painel')}?aba=geral")

    try:
        valor = Decimal(request.POST.get("saldo_inicial_financeiro", "0").replace(",", "."))
    except Exception:
        messages.error(request, "Valor inválido.")
        return redirect(f"{reverse('financeiro:painel')}?aba=geral")

    org.saldo_inicial_financeiro = valor
    org.save(update_fields=["saldo_inicial_financeiro"])
    messages.success(request, "Saldo inicial atualizado.")
    return redirect(f"{reverse('financeiro:painel')}?aba=geral")


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def lancamento_criar(request):
    org = organizacao_do_usuario(request)
    ano = request.GET.get("ano") or datetime.date.today().year
    mes = request.GET.get("mes") or datetime.date.today().month

    if request.method == "POST":
        form = LancamentoForm(request.POST, organizacao=org)
        if form.is_valid():
            lancamento = form.save(commit=False)
            lancamento.organizacao = org
            lancamento.save()
            messages.success(request, "Lançamento criado.")
            return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos&ano={lancamento.data.year}&mes={lancamento.data.month}")
    else:
        form = LancamentoForm(organizacao=org, initial={"data": datetime.date(int(ano), int(mes), min(datetime.date.today().day, 28))})

    return render(request, "financeiro/lancamento_form.html", {"form": form, "titulo": "Novo lançamento"})


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def lancamento_editar(request, pk):
    org = organizacao_do_usuario(request)
    lancamento = get_object_or_404(Lancamento, pk=pk, organizacao=org)

    if not usuario_e_administrador(request):
        messages.error(request, "Só administradores podem editar um lançamento já salvo.")
        return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos&ano={lancamento.data.year}&mes={lancamento.data.month}")

    if request.method == "POST":
        form = LancamentoForm(request.POST, instance=lancamento, organizacao=org)
        if form.is_valid():
            lancamento = form.save()
            messages.success(request, "Lançamento atualizado.")
            return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos&ano={lancamento.data.year}&mes={lancamento.data.month}")
    else:
        form = LancamentoForm(instance=lancamento, organizacao=org)

    return render(request, "financeiro/lancamento_form.html", {"form": form, "titulo": "Editar lançamento", "lancamento": lancamento})


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
@require_POST
def lancamento_excluir(request, pk):
    org = organizacao_do_usuario(request)
    lancamento = get_object_or_404(Lancamento, pk=pk, organizacao=org)

    if not usuario_e_administrador(request):
        messages.error(request, "Só administradores podem excluir um lançamento já salvo.")
        return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos&ano={lancamento.data.year}&mes={lancamento.data.month}")

    ano, mes = lancamento.data.year, lancamento.data.month
    lancamento.delete()
    messages.success(request, "Lançamento excluído.")
    return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos&ano={ano}&mes={mes}")


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def banco_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = BancoForm(request.POST, organizacao=org)
        if form.is_valid():
            banco = form.save(commit=False)
            banco.organizacao = org
            banco.save()
            messages.success(request, "Banco cadastrado.")
            return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos")
    else:
        form = BancoForm(organizacao=org)
    return render(request, "financeiro/banco_form.html", {"form": form})


@login_required
@modulo_ativo_obrigatorio("modulo_financeiro_ativo", "Controle Financeiro")
def categoria_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = CategoriaFinanceiraForm(request.POST, organizacao=org)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.organizacao = org
            categoria.save()
            messages.success(request, "Categoria cadastrada.")
            return redirect(f"{reverse('financeiro:painel')}?aba=lancamentos")
    else:
        form = CategoriaFinanceiraForm(organizacao=org)
    return render(request, "financeiro/categoria_form.html", {"form": form})
