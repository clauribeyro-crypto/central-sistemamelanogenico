import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario
from financeiro.views import MESES

from .forms import EntradaEstoqueForm, ProducaoPendenteForm, ProdutoForm, RecompraForm, VendaProdutoForm
from .models import Produto, ProducaoPendente, Recompra, VendaProduto

ABAS = ("geral", "estoque", "producao", "recompras", "vendas")


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

    if aba == "vendas":
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

        vendas_do_mes = VendaProduto.objects.filter(
            organizacao=org, data__year=ano, data__month=mes,
        ).select_related("produto", "paciente")

        contexto.update({
            "ano": ano,
            "mes": mes,
            "mes_nome": dict(MESES)[mes],
            "meses": MESES,
            "anos": range(hoje.year - 3, hoje.year + 2),
            "vendas_do_mes": vendas_do_mes,
            "total_unidades_mes": sum(v.quantidade for v in vendas_do_mes),
            "total_vendido_mes": sum((v.valor_total for v in vendas_do_mes), 0),
        })

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


@login_required
def venda_criar(request):
    """
    Registra uma venda de produto e desconta a quantidade do estoque — é
    isso que faltava pra estoque_atual bater com o que realmente saiu
    vendido. A data é editável pra dar pra lançar vendas de meses passados
    (ex.: reconstituir setembro) com a data certa de cada venda.
    """
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = VendaProdutoForm(request.POST, organizacao=org)
        if form.is_valid():
            venda = form.save(commit=False)
            venda.organizacao = org
            venda.save()
            produto = venda.produto
            produto.estoque_atual = produto.estoque_atual - venda.quantidade
            produto.save(update_fields=["estoque_atual"])
            if produto.estoque_atual < 0:
                messages.warning(
                    request,
                    f'Venda registrada, mas o estoque de "{produto.nome}" ficou negativo '
                    f"({produto.estoque_atual}) — o estoque atual dele estava contando a menos "
                    "do que o que realmente tinha. Ajuste com uma entrada de estoque.",
                )
            else:
                messages.success(request, "Venda registrada.")
            return redirect(
                f"{reverse('estoque:painel')}?aba=vendas&ano={venda.data.year}&mes={venda.data.month}"
            )
    else:
        form = VendaProdutoForm(organizacao=org)

    precos_produtos = {
        p.pk: {"pix": str(p.preco_pix), "cartao": str(p.preco_cartao)}
        for p in Produto.objects.filter(organizacao=org, ativo=True)
    }
    return render(request, "estoque/venda_form.html", {"form": form, "precos_produtos": precos_produtos})


@login_required
@require_POST
def venda_excluir(request, pk):
    """Apaga uma venda lançada por engano e devolve a quantidade ao estoque."""
    org = organizacao_do_usuario(request)
    venda = get_object_or_404(VendaProduto.objects.select_related("produto"), pk=pk, organizacao=org)
    produto = venda.produto
    produto.estoque_atual += venda.quantidade
    produto.save(update_fields=["estoque_atual"])
    ano, mes = venda.data.year, venda.data.month
    venda.delete()
    messages.success(request, "Venda excluída e quantidade devolvida ao estoque.")
    return redirect(f"{reverse('estoque:painel')}?aba=vendas&ano={ano}&mes={mes}")
