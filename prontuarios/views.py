from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from contas.utils import organizacao_do_usuario
from pacientes.models import Paciente

from .forms import AtendimentoForm
from .models import Atendimento


@login_required
def lista(request):
    """Tela de prontuários: lista de atendimentos recentes de todas as pacientes."""
    org = organizacao_do_usuario(request)
    busca = request.GET.get("q", "").strip()

    atendimentos = Atendimento.objects.filter(organizacao=org).select_related(
        "paciente", "profissional"
    )
    if busca:
        atendimentos = atendimentos.filter(
            Q(paciente__nome__icontains=busca) | Q(paciente__telefone__icontains=busca)
        )
    atendimentos = atendimentos.order_by("-data_hora")[:100]

    pacientes_json = list(
        Paciente.objects.filter(organizacao=org, ativo=True)
        .order_by("nome")
        .values("id", "nome", "telefone")
    )
    return render(request, "prontuarios/lista.html", {
        "atendimentos": atendimentos,
        "busca": busca,
        "pacientes_json": pacientes_json,
    })


def _redirecionar_apos_salvar(paciente):
    # Só a Ficha da paciente tem aba de Anamnese pra mostrar o atendimento
    # recém-criado quando a paciente tem um programa ativo; sem isso, a
    # tela de prontuários (lista geral) é sempre o destino que funciona.
    if paciente.acompanhamento_atual:
        return f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=anamnese"
    return reverse("prontuarios:lista")


@login_required
def criar(request, paciente_pk):
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=paciente_pk, organizacao=org)

    if request.method == "POST":
        form = AtendimentoForm(request.POST, organizacao=org, paciente=paciente)
        if form.is_valid():
            atendimento = form.save(commit=False)
            atendimento.organizacao = org
            atendimento.paciente = paciente
            atendimento.save()
            messages.success(request, "Atendimento registrado no prontuário.")
            return redirect(_redirecionar_apos_salvar(paciente))
    else:
        form = AtendimentoForm(
            organizacao=org, paciente=paciente,
            initial={"data_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M")},
        )
    return render(request, "prontuarios/form.html", {
        "paciente": paciente, "form": form, "atendimento": None,
    })


@login_required
def editar(request, pk):
    org = organizacao_do_usuario(request)
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    paciente = atendimento.paciente

    if request.method == "POST":
        form = AtendimentoForm(
            request.POST, instance=atendimento, organizacao=org, paciente=paciente
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Atendimento atualizado.")
            return redirect(_redirecionar_apos_salvar(paciente))
    else:
        form = AtendimentoForm(instance=atendimento, organizacao=org, paciente=paciente)
    return render(request, "prontuarios/form.html", {
        "paciente": paciente, "form": form, "atendimento": atendimento,
    })
