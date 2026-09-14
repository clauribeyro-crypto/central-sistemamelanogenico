from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from contas.utils import organizacao_do_usuario
from financeiro.models import Pagamento
from programas.models import Acompanhamento, CustoAcompanhamento

from .forms import IniciarProtocoloForm
from .models import Paciente

ABAS = [
    ("geral", "Visão geral"),
    ("anamnese", "Anamnese"),
    ("modulacao", "Modulação"),
    ("feedbacks", "Feedbacks"),
    ("fotos", "Fotos"),
    ("produtos", "Produtos"),
    ("financeiro", "Financeiro"),
    ("historico", "Histórico"),
]
ABAS_PRONTAS = {"geral", "anamnese", "produtos", "financeiro", "historico"}


@login_required
def lista(request):
    org = organizacao_do_usuario(request)
    busca = request.GET.get("q", "").strip()
    pacientes = Paciente.objects.filter(organizacao=org, ativo=True).order_by("nome")
    if busca:
        pacientes = pacientes.filter(Q(nome__icontains=busca) | Q(telefone__icontains=busca))
    return render(request, "pacientes/lista.html", {"pacientes": pacientes, "busca": busca})


@login_required
def ficha(request, pk):
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=pk, organizacao=org)
    acompanhamento = paciente.acompanhamento_atual

    aba = request.GET.get("aba", "geral")
    if aba not in dict(ABAS):
        aba = "geral"

    contexto = {
        "paciente": paciente,
        "acompanhamento": acompanhamento,
        "abas": ABAS,
        "aba_atual": aba,
        "aba_pronta": aba in ABAS_PRONTAS,
        "jornada": acompanhamento.jornada() if acompanhamento else None,
        "alertas": acompanhamento.alertas() if acompanhamento else [],
    }

    if acompanhamento and aba == "financeiro":
        pagamentos = Pagamento.objects.filter(acompanhamento=acompanhamento).order_by("-data_vencimento")
        custos = CustoAcompanhamento.objects.filter(acompanhamento=acompanhamento).order_by("-data")
        recebido = pagamentos.filter(status=Pagamento.Status.PAGO).aggregate(t=Sum("valor"))["t"] or 0
        total_custos = custos.aggregate(t=Sum("valor"))["t"] or 0
        contexto.update({
            "pagamentos": pagamentos,
            "custos": custos,
            "recebido": recebido,
            "a_receber": acompanhamento.valor_contratado - acompanhamento.desconto - recebido,
            "total_custos": total_custos,
            "resultado": recebido - total_custos,
        })

    if aba == "anamnese":
        contexto["atendimentos"] = paciente.atendimentos.select_related("profissional").order_by("-data_hora")

    if acompanhamento and aba == "produtos":
        contexto["kits"] = acompanhamento.kits_previstos.order_by("numero")

    if acompanhamento and aba == "historico":
        eventos = [{"data": acompanhamento.data_inicio, "texto": f"Início do acompanhamento — {acompanhamento.programa.nome}"}]
        for c in acompanhamento.consultas_previstas.select_related("consulta"):
            if c.status == c.Status.REALIZADA and c.consulta:
                eventos.append({"data": c.consulta.data_hora.date(), "texto": f"Consulta {c.numero} realizada"})
        for k in acompanhamento.kits_previstos.all():
            if k.status == k.Status.ENVIADO and k.data_envio:
                eventos.append({"data": k.data_envio, "texto": f"Kit {k.numero} enviado"})
        contexto["eventos"] = sorted(eventos, key=lambda e: e["data"])

    if acompanhamento and aba == "geral":
        pagamentos = Pagamento.objects.filter(acompanhamento=acompanhamento)
        recebido = pagamentos.filter(status=Pagamento.Status.PAGO).aggregate(t=Sum("valor"))["t"] or 0
        custos_total = CustoAcompanhamento.objects.filter(
            acompanhamento=acompanhamento
        ).aggregate(t=Sum("valor"))["t"] or 0
        contexto.update({
            "recebido": recebido,
            "a_receber": acompanhamento.valor_contratado - acompanhamento.desconto - recebido,
            "total_custos": custos_total,
        })

    return render(request, "pacientes/ficha.html", contexto)


@login_required
def iniciar_protocolo(request, pk):
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=pk, organizacao=org)

    if request.method == "POST":
        form = IniciarProtocoloForm(request.POST, organizacao=org)
        if form.is_valid():
            Acompanhamento.iniciar(
                paciente=paciente,
                programa=form.cleaned_data["programa"],
                data_inicio=form.cleaned_data["data_inicio"],
                valor_contratado=form.cleaned_data["valor_contratado"],
                desconto=form.cleaned_data["desconto"] or 0,
                forma_pagamento=form.cleaned_data["forma_pagamento"],
                observacoes=form.cleaned_data["observacoes"],
            )
            messages.success(request, "Protocolo de acompanhamento iniciado.")
            return redirect("pacientes:ficha", pk=paciente.pk)
    else:
        form = IniciarProtocoloForm(organizacao=org)

    return render(request, "pacientes/iniciar_protocolo.html", {"paciente": paciente, "form": form})
