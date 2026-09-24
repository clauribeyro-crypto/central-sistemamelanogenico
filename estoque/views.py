import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario
from financeiro.models import Pagamento, Recebimento
from financeiro.views import MESES

from .forms import (
    EntradaEstoqueForm, ItemVendaFormSet, ProducaoPendenteForm, ProdutoForm, RecompraForm, VendaForm,
)
from .models import ItemVenda, Produto, ProducaoPendente, Recompra, Venda

ABAS = ("geral", "estoque", "producao", "recompras", "vendas")

# Compra de produto só distingue Pix/dinheiro de cartão (pra achar o preço na
# tabela do Produto); o Financeiro é mais detalhado (débito/crédito etc.) —
# esse mapa converte pro valor mais próximo quando registra o recebimento.
MAPA_FORMA_PAGAMENTO_FINANCEIRO = {
    Venda.FormaPagamento.PIX: Pagamento.FormaPagamento.PIX,
    Venda.FormaPagamento.CARTAO: Pagamento.FormaPagamento.CREDITO,
}


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

        vendas_do_mes = list(
            Venda.objects.filter(organizacao=org, data__year=ano, data__month=mes)
            .select_related("paciente").prefetch_related("itens__produto")
        )

        contexto.update({
            "ano": ano,
            "mes": mes,
            "mes_nome": dict(MESES)[mes],
            "meses": MESES,
            "anos": range(hoje.year - 3, hoje.year + 2),
            "vendas_do_mes": vendas_do_mes,
            "total_unidades_mes": sum(v.quantidade_total for v in vendas_do_mes),
            "total_vendido_mes": sum((v.valor_total for v in vendas_do_mes), Decimal("0.00")),
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
    Registra uma compra (um ou mais produtos juntos) e desconta cada
    quantidade do estoque — é isso que faltava pra estoque_atual bater com
    o que realmente saiu vendido. A data é editável pra dar pra lançar
    compras de meses passados (ex.: reconstituir setembro) com a data certa.

    Quando é de uma paciente cadastrada, gera um Pagamento no Financeiro
    (mesmo mecanismo de tratamento/consulta) — dá pra registrar só uma
    parte agora e o resto depois, em vez de exigir pagamento à vista.
    Comprador avulso não gera Pagamento: sempre tratado como pago na hora.
    """
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = VendaForm(request.POST, organizacao=org)
        formset = ItemVendaFormSet(request.POST, form_kwargs={"organizacao": org})
        if form.is_valid() and formset.is_valid():
            itens_preenchidos = [
                dados for dados in formset.cleaned_data if dados.get("produto")
            ]
            if not itens_preenchidos:
                messages.error(request, "Adicione pelo menos um produto à compra.")
            else:
                venda = form.save(commit=False)
                venda.organizacao = org
                venda.save()

                preco_campo = "preco_cartao" if venda.forma_pagamento == Venda.FormaPagamento.CARTAO else "preco_pix"
                estoques_negativos = []
                for dados in itens_preenchidos:
                    produto = dados["produto"]
                    quantidade = dados["quantidade"]
                    ItemVenda.objects.create(
                        organizacao=org, venda=venda, produto=produto,
                        quantidade=quantidade, valor_unitario=getattr(produto, preco_campo),
                    )
                    produto.estoque_atual = produto.estoque_atual - quantidade
                    produto.save(update_fields=["estoque_atual"])
                    if produto.estoque_atual < 0:
                        estoques_negativos.append(produto.nome)

                if venda.paciente_id:
                    pagamento = Pagamento.objects.create(
                        organizacao=org, paciente=venda.paciente, venda=venda,
                        valor=venda.valor_total,
                        forma_pagamento=MAPA_FORMA_PAGAMENTO_FINANCEIRO[venda.forma_pagamento],
                        status=Pagamento.Status.PENDENTE, data_vencimento=venda.data,
                    )
                    valor_recebido = form.cleaned_data.get("valor_recebido_agora")
                    if valor_recebido:
                        Recebimento.objects.create(
                            organizacao=org, pagamento=pagamento, valor=valor_recebido,
                            data=venda.data,
                            forma_pagamento=MAPA_FORMA_PAGAMENTO_FINANCEIRO[venda.forma_pagamento],
                        )

                if estoques_negativos:
                    messages.warning(
                        request,
                        "Compra registrada, mas o estoque ficou negativo em: "
                        + ", ".join(estoques_negativos)
                        + " — o estoque atual deles estava contando a menos do que o que realmente"
                        " tinha. Ajuste com uma entrada de estoque.",
                    )
                else:
                    messages.success(request, "Compra registrada.")
                return redirect(
                    f"{reverse('estoque:painel')}?aba=vendas&ano={venda.data.year}&mes={venda.data.month}"
                )
    else:
        form = VendaForm(organizacao=org)
        formset = ItemVendaFormSet(form_kwargs={"organizacao": org})

    precos_produtos = {
        p.pk: {"pix": str(p.preco_pix), "cartao": str(p.preco_cartao)}
        for p in Produto.objects.filter(organizacao=org, ativo=True)
    }
    return render(request, "estoque/venda_form.html", {
        "form": form, "formset": formset, "precos_produtos": precos_produtos,
    })


@login_required
@require_POST
def venda_excluir(request, pk):
    """Apaga uma compra lançada por engano, devolve as quantidades ao estoque e apaga o pagamento vinculado."""
    org = organizacao_do_usuario(request)
    venda = get_object_or_404(
        Venda.objects.prefetch_related("itens__produto"), pk=pk, organizacao=org
    )
    for item in venda.itens.all():
        item.produto.estoque_atual += item.quantidade
        item.produto.save(update_fields=["estoque_atual"])
    Pagamento.objects.filter(venda=venda).delete()
    ano, mes = venda.data.year, venda.data.month
    venda.delete()
    messages.success(request, "Compra excluída, quantidades devolvidas ao estoque e pagamento removido.")
    return redirect(f"{reverse('estoque:painel')}?aba=vendas&ano={ano}&mes={mes}")
