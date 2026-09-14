from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from contas.utils import organizacao_do_usuario

from .forms import ProfissionalForm
from .models import Profissional


@login_required
def lista(request):
    org = organizacao_do_usuario(request)
    profissionais = Profissional.objects.filter(organizacao=org).order_by("nome")
    return render(request, "profissionais/lista.html", {"profissionais": profissionais})


@login_required
def criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = ProfissionalForm(request.POST)
        if form.is_valid():
            profissional = form.save(commit=False)
            profissional.organizacao = org
            profissional.save()
            messages.success(request, "Profissional cadastrado.")
            return redirect("profissionais:lista")
    else:
        form = ProfissionalForm()
    return render(request, "profissionais/form.html", {"form": form, "profissional": None})


@login_required
def editar(request, pk):
    org = organizacao_do_usuario(request)
    profissional = get_object_or_404(Profissional, pk=pk, organizacao=org)
    if request.method == "POST":
        form = ProfissionalForm(request.POST, instance=profissional)
        if form.is_valid():
            form.save()
            messages.success(request, "Profissional atualizado.")
            return redirect("profissionais:lista")
    else:
        form = ProfissionalForm(instance=profissional)
    return render(request, "profissionais/form.html", {"form": form, "profissional": profissional})
