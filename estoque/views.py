from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario

from .forms import EntradaEstoqueForm, ProducaoPendenteForm, ProdutoForm, RecompraForm
from .models import Produto, ProducaoPendente, Recompra

ABAS = ("geral", "estoque", "producao", "recompras")


@login_required
def painel(request):
    org = organizacao_do_usuario(request)
    aba = request.GET.get("aba", "geral")
    if aba not in ABAS:
        aba = "geral"

    produtos = Produto.objects.filter(organizacao=org, ativo=True)
    producoes_pendentes = ProducaoPendente.objects.filter(organizacao=org).exclude(
        status=ProducaoPendente.Status.PRONTO
    ).select_related("produto")
    recompras_abertas = Recompra.objects.filter(
        organizacao=org, data_realizada__isnull=True
    ).select_related("paciente", "produto")

    produtos_criticos_baixos = [p for p in produtos if p.nivel_estoque in ("BAIXO", "CRITICO")]
    recompras_proximas = [r for r in recompras_abertas if r.status == "PROXIMA_DO_PRAZO"]
    recompras_atrasadas = [r for r in recompras_abertas if r.status == "ATRASADA"]

    contexto = {
        "aba_atual": aba,
        "produtos": produtos,
        "producoes_pendentes": producoes_pendentes,
        "recompras_abertas": recompras_abertas,
        "produtos_criticos_baixos": produtos_criticos_baixos,
        "unidades_em_producao": sum(p.quantidade for p in producoes_pendentes),
        "recompras_proximas": recompras_proximas,
        "recompras_atrasadas": recompras_atrasadas,
    }
    return render(request, "estoque/painel.html", contexto)


@login_required
def produto_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.organizacao = org
            produto.save()
            messages.success(request, "Produto cadastrado.")
            return redirect(f"{reverse('estoque:painel')}?aba=estoque")
    else:
        form = ProdutoForm()
    return render(request, "estoque/produto_form.html", {"form": form, "produto": None})


@login_required
def produto_editar(request, pk):
    org = organizacao_do_usuario(request)
    produto = get_object_or_404(Produto, pk=pk, organizacao=org)
    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, "Produto atualizado.")
            return redirect(f"{reverse('estoque:painel')}?aba=estoque")
    else:
        form = ProdutoForm(instance=produto)
    return render(request, "estoque/produto_form.html", {"form": form, "produto": produto})


@login_required
@require_POST
def entrada_estoque(request, pk):
    """Soma manualmente ao estoque (ex.: comprou embalagem pronta, sem passar pela produção pendente)."""
    org = organizacao_do_usuario(request)
    produto = get_object_or_404(Produto, pk=pk, organizacao=org)
    form = EntradaEstoqueForm(request.POST)
    if form.is_valid():
        quantidade = form.cleaned_data["quantidade"]
        produto.estoque_atual += quantidade
        produto.save(update_fields=["estoque_atual"])
        messages.success(request, f'Adicionadas {quantidade} unidades de "{produto.nome}".')
    else:
        messages.error(request, "Quantidade inválida.")
    return redirect(f"{reverse('estoque:painel')}?aba=estoque")


@login_required
def producao_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = ProducaoPendenteForm(request.POST, organizacao=org)
        if form.is_valid():
            producao = form.save(commit=False)
            producao.organizacao = org
            producao.save()
            messages.success(request, "Produção registrada.")
            return redirect(f"{reverse('estoque:painel')}?aba=producao")
    else:
        form = ProducaoPendenteForm(organizacao=org)
    return render(request, "estoque/producao_form.html", {"form": form})


@login_required
@require_POST
def producao_marcar_pronto(request, pk):
    org = organizacao_do_usuario(request)
    producao = get_object_or_404(
        ProducaoPendente.objects.select_related("produto"), pk=pk, organizacao=org
    )
    producao.marcar_pronto()
    messages.success(
        request, f'{producao.quantidade} unidades de "{producao.produto.nome}" somadas ao estoque.'
    )
    return redirect(f"{reverse('estoque:painel')}?aba=producao")


@login_required
def recompra_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = RecompraForm(request.POST, organizacao=org)
        if form.is_valid():
            recompra = form.save(commit=False)
            recompra.organizacao = org
            recompra.save()
            messages.success(request, "Recompra agendada.")
            return redirect(f"{reverse('estoque:painel')}?aba=recompras")
    else:
        form = RecompraForm(organizacao=org)
    return render(request, "estoque/recompra_form.html", {"form": form})


@login_required
@require_POST
def recompra_marcar_comprada(request, pk):
    org = organizacao_do_usuario(request)
    recompra = get_object_or_404(
        Recompra.objects.select_related("produto", "paciente"), pk=pk, organizacao=org
    )
    recompra.marcar_comprada()
    messages.success(request, f"Recompra de {recompra.paciente} registrada — próximo ciclo já agendado.")
    return redirect(f"{reverse('estoque:painel')}?aba=recompras")
