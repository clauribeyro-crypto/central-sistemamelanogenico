from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from agenda.models import TipoConsulta
from contas.utils import organizacao_do_usuario, usuario_e_administrador

from .forms import AvaliacaoFaseForm, FeedbackForm, PlanoFaseForm, ProgramaForm, TipoConsultaForm
from .models import Acompanhamento, Feedback, FaseModulacao, Programa


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


ACOES_STATUS = {
    "finalizar": (Acompanhamento.Status.FINALIZADO, "Acompanhamento finalizado."),
    "manutencao": (Acompanhamento.Status.MANUTENCAO, "Acompanhamento movido para manutenção."),
    "aguardando_decisao": (
        Acompanhamento.Status.AGUARDANDO_DECISAO,
        "Acompanhamento marcado como aguardando decisão da paciente.",
    ),
    "renovar": (Acompanhamento.Status.RENOVADO, "Acompanhamento marcado como renovado."),
    "migrar": (Acompanhamento.Status.MIGRADO, "Acompanhamento marcado como migrado para outro programa."),
}


@login_required
@require_POST
def mudar_status_acompanhamento(request, pk):
    """
    Ações de fim/continuidade de programa (Doc 1 §11): finalizar, colocar em
    manutenção, marcar aguardando decisão, ou renovar/migrar — nesses dois
    últimos casos, encerra o acompanhamento atual com o status certo e manda
    direto pra tela de iniciar um novo (mesma paciente, sem cadastro novo,
    o histórico do acompanhamento anterior continua na ficha).
    """
    org = organizacao_do_usuario(request)
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    acao = request.POST.get("acao")
    if acao not in ACOES_STATUS:
        messages.error(request, "Ação inválida.")
        return redirect("pacientes:ficha", pk=acompanhamento.paciente.pk)

    novo_status, mensagem = ACOES_STATUS[acao]
    acompanhamento.status = novo_status
    acompanhamento.status_atualizado_em = timezone.now()
    acompanhamento.save(update_fields=["status", "status_atualizado_em"])
    messages.success(request, mensagem)

    if acao in ("renovar", "migrar"):
        return redirect("pacientes:iniciar_protocolo", pk=acompanhamento.paciente.pk)
    return redirect("pacientes:ficha", pk=acompanhamento.paciente.pk)


@login_required
def fase_detalhe(request, pk):
    """
    Plano e avaliação de uma fase da modulação. Definir o plano ou registrar
    a avaliação pela primeira vez é livre pra qualquer profissional logado;
    alterar um plano ou uma avaliação já salvos exige administrador — mesma
    regra do Atendimento e da Anamnese, porque isso já é histórico clínico.
    """
    org = organizacao_do_usuario(request)
    fase = get_object_or_404(
        FaseModulacao.objects.select_related("modulacao__acompanhamento__paciente"),
        pk=pk, modulacao__acompanhamento__organizacao=org,
    )
    paciente = fase.modulacao.acompanhamento.paciente
    pode_editar_plano = fase.status == FaseModulacao.Status.PENDENTE or usuario_e_administrador(request)
    pode_editar_avaliacao = (
        fase.status != FaseModulacao.Status.CONCLUIDA or usuario_e_administrador(request)
    )

    fase_anterior = None
    if fase.numero > 1:
        fase_anterior = fase.modulacao.fases.filter(numero=fase.numero - 1).first()

    if request.method == "POST":
        qual_form = request.POST.get("form")
        if qual_form == "plano":
            if not pode_editar_plano:
                messages.error(request, "Só um administrador da clínica pode editar o plano dessa fase.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_plano = PlanoFaseForm(request.POST, instance=fase)
            if form_plano.is_valid():
                fase.iniciar_fase(
                    plano=form_plano.cleaned_data["plano"],
                    data_inicio=form_plano.cleaned_data.get("data_inicio"),
                )
                messages.success(request, f"Plano da fase {fase.numero} salvo.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_avaliacao = AvaliacaoFaseForm(instance=fase)
        elif qual_form == "avaliacao":
            if fase.status == FaseModulacao.Status.PENDENTE:
                messages.error(request, "Defina o plano dessa fase antes de registrar a avaliação.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            if not pode_editar_avaliacao:
                messages.error(request, "Só um administrador da clínica pode editar a avaliação dessa fase.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_avaliacao = AvaliacaoFaseForm(request.POST, instance=fase)
            if form_avaliacao.is_valid():
                fase.concluir_com_avaliacao(
                    resultado=form_avaliacao.cleaned_data["resultado"],
                    principais_melhoras=form_avaliacao.cleaned_data["principais_melhoras"],
                    o_que_trabalhar=form_avaliacao.cleaned_data["o_que_trabalhar"],
                )
                messages.success(request, f"Avaliação da fase {fase.numero} registrada.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_plano = PlanoFaseForm(instance=fase)
        else:
            messages.error(request, "Ação inválida.")
            return redirect("programas:fase_detalhe", pk=fase.pk)
    else:
        form_plano = PlanoFaseForm(instance=fase)
        form_avaliacao = AvaliacaoFaseForm(instance=fase)

    if not pode_editar_plano:
        for field in form_plano.fields.values():
            field.disabled = True
    if not pode_editar_avaliacao:
        for field in form_avaliacao.fields.values():
            field.disabled = True

    return render(request, "programas/fase_detalhe.html", {
        "paciente": paciente,
        "fase": fase,
        "fase_anterior": fase_anterior,
        "form_plano": form_plano,
        "form_avaliacao": form_avaliacao,
        "pode_editar_plano": pode_editar_plano,
        "pode_editar_avaliacao": pode_editar_avaliacao,
    })


@login_required
def feedback_criar(request, acompanhamento_pk):
    org = organizacao_do_usuario(request)
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=acompanhamento_pk, organizacao=org
    )
    if request.method == "POST":
        form = FeedbackForm(request.POST, acompanhamento=acompanhamento)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.acompanhamento = acompanhamento
            feedback.save()
            messages.success(request, "Feedback registrado.")
            return redirect(f"{reverse('pacientes:ficha', args=[acompanhamento.paciente.pk])}?aba=feedbacks")
    else:
        form = FeedbackForm(
            acompanhamento=acompanhamento,
            initial={"data_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M")},
        )
    return render(request, "programas/feedback_form.html", {
        "paciente": acompanhamento.paciente, "form": form, "feedback": None,
    })


@login_required
def feedback_editar(request, pk):
    """Registrar um feedback novo é livre; editar um já salvo exige administrador."""
    org = organizacao_do_usuario(request)
    feedback = get_object_or_404(
        Feedback.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    acompanhamento = feedback.acompanhamento
    pode_editar = usuario_e_administrador(request)

    if request.method == "POST":
        if not pode_editar:
            messages.error(request, "Só um administrador da clínica pode editar um feedback já salvo.")
            return redirect("programas:feedback_editar", pk=feedback.pk)
        form = FeedbackForm(request.POST, instance=feedback, acompanhamento=acompanhamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Feedback atualizado.")
            return redirect(f"{reverse('pacientes:ficha', args=[acompanhamento.paciente.pk])}?aba=feedbacks")
    else:
        form = FeedbackForm(instance=feedback, acompanhamento=acompanhamento)
        if not pode_editar:
            for field in form.fields.values():
                field.disabled = True
    return render(request, "programas/feedback_form.html", {
        "paciente": acompanhamento.paciente, "form": form, "feedback": feedback, "pode_editar": pode_editar,
    })
