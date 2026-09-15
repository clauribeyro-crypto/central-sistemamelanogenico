from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario, usuario_e_administrador
from pacientes.models import Paciente

from .forms import AnamneseForm, AtendimentoForm, DocumentoForm
from .models import Anamnese, Atendimento, Documento


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
    """
    Ver um atendimento já registrado é livre pra qualquer profissional
    logado — só a ação de salvar uma alteração nele é que fica restrita a
    quem administra a clínica (ver `usuario_e_administrador`), porque isso
    já é histórico clínico, diferente de criar um atendimento novo.
    """
    org = organizacao_do_usuario(request)
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    paciente = atendimento.paciente
    pode_editar = usuario_e_administrador(request)

    if request.method == "POST":
        if not pode_editar:
            messages.error(
                request,
                "Só um administrador da clínica pode editar um atendimento já salvo.",
            )
            return redirect("prontuarios:editar", pk=atendimento.pk)
        form = AtendimentoForm(
            request.POST, instance=atendimento, organizacao=org, paciente=paciente
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Atendimento atualizado.")
            return redirect(_redirecionar_apos_salvar(paciente))
    else:
        form = AtendimentoForm(instance=atendimento, organizacao=org, paciente=paciente)
        if not pode_editar:
            for field in form.fields.values():
                field.disabled = True
    return render(request, "prontuarios/form.html", {
        "paciente": paciente, "form": form, "atendimento": atendimento,
        "pode_editar": pode_editar,
    })


@login_required
def anamnese(request, paciente_pk):
    """
    Levantamento estruturado de saúde — um registro por paciente. Preencher
    pela primeira vez é livre pra qualquer profissional logado; alterar uma
    anamnese já preenchida exige administrador (mesma regra do Atendimento).
    """
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=paciente_pk, organizacao=org)
    instancia = Anamnese.objects.filter(paciente=paciente).first()
    pode_editar = instancia is None or usuario_e_administrador(request)

    if request.method == "POST":
        if not pode_editar:
            messages.error(
                request, "Só um administrador da clínica pode editar a anamnese já salva."
            )
            return redirect("prontuarios:anamnese", paciente_pk=paciente.pk)
        form = AnamneseForm(request.POST, instance=instancia)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.organizacao = org
            registro.paciente = paciente
            registro.save()
            messages.success(request, "Anamnese salva.")
            return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=anamnese")
    else:
        form = AnamneseForm(instance=instancia)
        if not pode_editar:
            for field in form.fields.values():
                field.disabled = True
    return render(request, "prontuarios/anamnese_form.html", {
        "paciente": paciente, "form": form, "anamnese": instancia, "pode_editar": pode_editar,
    })


@login_required
def documento_criar(request, paciente_pk):
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=paciente_pk, organizacao=org)
    if request.method == "POST":
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.organizacao = org
            documento.paciente = paciente
            documento.enviado_por = request.user
            documento.save()
            messages.success(request, "Documento enviado.")
        else:
            messages.error(request, "Não deu pra enviar o documento — confira o formulário.")
    return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=documentos")


@login_required
@require_POST
def documento_excluir(request, pk):
    """Excluir um documento já enviado exige administrador — anexar um novo é livre."""
    org = organizacao_do_usuario(request)
    documento = get_object_or_404(
        Documento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    paciente = documento.paciente
    if not usuario_e_administrador(request):
        messages.error(request, "Só um administrador da clínica pode excluir um documento.")
        return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=documentos")
    documento.delete()
    messages.success(request, "Documento excluído.")
    return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=documentos")
