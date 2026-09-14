from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from agenda.models import TipoConsulta
from contas.utils import organizacao_do_usuario

from .forms import ProgramaForm, TipoConsultaForm
from .models import Programa


@login_required
def configuracoes(request):
    org = organizacao_do_usuario(request)
    aba = request.GET.get("aba", "tipos")
    if aba not in ("tipos", "planos"):
        aba = "tipos"

    contexto = {
        "aba_atual": aba,
        "tipos_consulta": TipoConsulta.objects.filter(organizacao=org).order_by("ordem", "nome"),
        "programas": Programa.objects.filter(organizacao=org).order_by("duracao_meses"),
    }
    return render(request, "programas/configuracoes.html", contexto)


@login_required
def tipo_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = TipoConsultaForm(request.POST)
        if form.is_valid():
            tipo = form.save(commit=False)
            tipo.organizacao = org
            tipo.save()
            messages.success(request, "Tipo de consulta cadastrado.")
            return redirect("programas:configuracoes")
    else:
        form = TipoConsultaForm()
    return render(request, "programas/tipo_form.html", {"form": form, "tipo": None})


@login_required
def tipo_editar(request, pk):
    org = organizacao_do_usuario(request)
    tipo = get_object_or_404(TipoConsulta, pk=pk, organizacao=org)
    if request.method == "POST":
        form = TipoConsultaForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de consulta atualizado.")
            return redirect("programas:configuracoes")
    else:
        form = TipoConsultaForm(instance=tipo)
    return render(request, "programas/tipo_form.html", {"form": form, "tipo": tipo})


@login_required
def plano_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = ProgramaForm(request.POST)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.organizacao = org
            plano.save()
            messages.success(request, "Plano de acompanhamento cadastrado.")
            return redirect("programas:configuracoes")
    else:
        form = ProgramaForm()
    return render(request, "programas/plano_form.html", {"form": form, "plano": None})


@login_required
def plano_editar(request, pk):
    org = organizacao_do_usuario(request)
    plano = get_object_or_404(Programa, pk=pk, organizacao=org)
    if request.method == "POST":
        form = ProgramaForm(request.POST, instance=plano)
        if form.is_valid():
            form.save()
            messages.success(request, "Plano de acompanhamento atualizado.")
            return redirect("programas:configuracoes")
    else:
        form = ProgramaForm(instance=plano)
    return render(request, "programas/plano_form.html", {"form": form, "plano": plano})
