from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from agenda.models import Consulta
from contas.utils import modulo_ativo_obrigatorio, organizacao_do_usuario, usuario_e_administrador
from financeiro.models import Pagamento, Recebimento
from leads.models import HistoricoLead
from programas.models import Acompanhamento, CustoAcompanhamento, FaseModulacao, FotoEvolucao
from prontuarios.models import Anamnese, Documento

from .forms import IniciarProtocoloForm, PacienteRapidoForm
from .models import Paciente

ABAS = [
    ("geral", "Visão geral"),
    ("anamnese", "Anamnese"),
    ("evolucao", "Evolução"),
    ("modulacao", "Modulação"),
    ("feedbacks", "Feedbacks"),
    ("consultas", "Consultas"),
    ("fotos", "Fotos"),
    ("documentos", "Exames/Documentos"),
    ("produtos", "Produtos"),
    ("financeiro", "Financeiro"),
    ("historico", "Histórico"),
]
ABAS_PRONTAS = {
    "geral", "anamnese", "evolucao", "modulacao", "feedbacks", "consultas", "fotos",
    "documentos", "produtos", "financeiro", "historico",
}


def _grafico_evolucao(registros, largura=640, altura=160, pad=24):
    """
    Coordenadas SVG já prontas pra desenhar as 3 linhas (energia, sono,
    digestão) do resumo visual da aba Evolução — `registros` deve vir em
    ordem cronológica (mais antigo primeiro). Só entram os check-ins com
    as 3 métricas calculáveis, pra manter o gráfico "simples" sem lidar
    com buracos na linha.
    """
    pontos = []
    for r in registros:
        energia, digestao = r.energia_media, r.digestao_media
        if energia is None or digestao is None or r.qualidade_sono is None:
            continue
        pontos.append({"data": r.criado_em, "energia": energia, "sono": r.qualidade_sono, "digestao": digestao})

    def linha(chave):
        n = len(pontos)
        partes = []
        for i, p in enumerate(pontos):
            x = pad if n <= 1 else pad + (largura - 2 * pad) * i / (n - 1)
            y = pad + (altura - 2 * pad) * (1 - p[chave] / 10)
            partes.append(f"{x:.1f},{y:.1f}")
        return " ".join(partes)

    return {
        "pontos": pontos,
        "largura": largura,
        "altura": altura,
        "energia_points": linha("energia"),
        "sono_points": linha("sono"),
        "digestao_points": linha("digestao"),
    }


def _financeiro_do_acompanhamento(acompanhamento):
    """
    Resumo financeiro do programa: recebido soma os recebimentos de verdade
    (não só pagamentos já 100% quitados), pra não esconder entradas parciais —
    mesmo bug já corrigido no relatório geral do Financeiro (financeiro/views.py).
    """
    recebido = Recebimento.objects.filter(
        pagamento__acompanhamento=acompanhamento
    ).aggregate(t=Sum("valor"))["t"] or 0
    total_custos = CustoAcompanhamento.objects.filter(
        acompanhamento=acompanhamento
    ).aggregate(t=Sum("valor"))["t"] or 0
    valor_vendido = acompanhamento.valor_contratado - acompanhamento.desconto
    return {
        "valor_vendido": valor_vendido,
        "recebido": recebido,
        "a_receber": valor_vendido - recebido,
        "total_custos": total_custos,
        "resultado": recebido - total_custos,
    }


@login_required
def lista(request):
    org = organizacao_do_usuario(request)
    busca = request.GET.get("q", "").strip()
    pacientes = Paciente.objects.filter(organizacao=org, ativo=True).order_by("nome")
    if busca:
        pacientes = pacientes.filter(Q(nome__icontains=busca) | Q(telefone__icontains=busca))
    form_rapido = PacienteRapidoForm(initial={"nome": busca} if busca and not pacientes else None)
    return render(request, "pacientes/lista.html", {
        "pacientes": pacientes, "busca": busca, "form_rapido": form_rapido,
    })


@login_required
def criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form_rapido = PacienteRapidoForm(request.POST)
        if form_rapido.is_valid():
            paciente = form_rapido.save(commit=False)
            paciente.organizacao = org
            paciente.save()
            messages.success(request, f"Paciente \"{paciente.nome}\" cadastrada.")
            return redirect("pacientes:ficha", pk=paciente.pk)
        messages.error(request, "Não deu pra cadastrar — confira o formulário.")
        busca = request.POST.get("nome", "")
        pacientes = Paciente.objects.filter(organizacao=org, ativo=True).order_by("nome")
        if busca:
            pacientes = pacientes.filter(Q(nome__icontains=busca) | Q(telefone__icontains=busca))
        return render(request, "pacientes/lista.html", {
            "pacientes": pacientes, "busca": busca, "form_rapido": form_rapido,
        })
    return redirect("pacientes:lista")


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
        "tem_algum_acompanhamento": paciente.acompanhamentos.exists(),
        "usuario_e_administrador": usuario_e_administrador(request),
        "abas": ABAS,
        "aba_atual": aba,
        "aba_pronta": aba in ABAS_PRONTAS,
        "jornada": acompanhamento.jornada() if acompanhamento else None,
        "alertas": acompanhamento.alertas() if acompanhamento else [],
    }

    if acompanhamento and aba == "financeiro":
        pagamentos = Pagamento.objects.filter(acompanhamento=acompanhamento).order_by("-data_vencimento")
        custos = CustoAcompanhamento.objects.filter(acompanhamento=acompanhamento).order_by("-data")
        contexto.update({
            "pagamentos": pagamentos,
            "custos": custos,
            **_financeiro_do_acompanhamento(acompanhamento),
        })

    if aba == "anamnese":
        contexto["anamnese"] = Anamnese.objects.filter(paciente=paciente).first()
        contexto["link_anamnese_ativo"] = paciente.links_anamnese.filter(
            ativo=True, preenchido_em__isnull=True
        ).order_by("-criado_em").first()
        if contexto["link_anamnese_ativo"]:
            contexto["link_anamnese_url"] = request.build_absolute_uri(
                reverse("prontuarios:anamnese_publica", args=[contexto["link_anamnese_ativo"].token])
            )
        contexto["atendimentos"] = paciente.atendimentos.select_related("profissional").order_by("-data_hora")

    if aba == "evolucao":
        contexto["link_checkin"] = getattr(paciente, "link_checkin", None)
        if contexto["link_checkin"]:
            contexto["link_checkin_url"] = request.build_absolute_uri(
                reverse("prontuarios:checkin_publico", args=[contexto["link_checkin"].token])
            )
        registros = list(paciente.registros_evolucao.select_related("criado_por").order_by("-criado_em"))
        contexto["registros_evolucao"] = registros
        contexto["grafico_evolucao"] = _grafico_evolucao(list(reversed(registros)))

    if acompanhamento and aba == "modulacao":
        contexto["modulacoes"] = acompanhamento.modulacoes.prefetch_related("fases").order_by("numero")
        contexto["resumo_evolucao"] = FaseModulacao.objects.filter(
            modulacao__acompanhamento=acompanhamento, status=FaseModulacao.Status.CONCLUIDA
        ).select_related("modulacao").order_by("modulacao__numero", "numero")

    if acompanhamento and aba == "feedbacks":
        contexto["feedbacks"] = acompanhamento.feedbacks.select_related("fase").order_by("-data_hora")

    if acompanhamento and aba == "fotos":
        fotos = list(acompanhamento.fotos.order_by("angulo", "momento", "-criado_em"))
        mais_recente_por_combo = {}
        for f in fotos:
            chave = (f.angulo, f.momento)
            if chave not in mais_recente_por_combo:
                mais_recente_por_combo[chave] = f
        contexto["grade_fotos"] = [
            {
                "angulo": angulo,
                "angulo_label": angulo_label,
                "colunas": [
                    {"momento": momento, "momento_label": momento_label, "foto": mais_recente_por_combo.get((angulo, momento))}
                    for momento, momento_label in FotoEvolucao.Momento.choices
                ],
            }
            for angulo, angulo_label in FotoEvolucao.Angulo.choices
        ]
        contexto["fotos_todas"] = fotos

    if aba == "documentos":
        contexto["documentos"] = paciente.documentos.order_by("-criado_em")

    if aba == "consultas":
        if acompanhamento:
            contexto["consultas_previstas"] = acompanhamento.consultas_previstas.select_related(
                "consulta__profissional", "consulta__tipo_consulta"
            ).order_by("numero")
        contexto["consultas_agenda"] = Consulta.objects.filter(
            organizacao=org, paciente=paciente
        ).exclude(status=Consulta.Status.CANCELADA).select_related(
            "profissional", "tipo_consulta"
        ).order_by("-data_hora")

    if acompanhamento and aba == "produtos":
        contexto["kits"] = acompanhamento.kits_previstos.prefetch_related("itens__produto").order_by("numero")

    if aba == "historico":
        eventos = []

        # Lado do lead: só os marcos (entrada e agendamento), não o log de
        # cada tentativa de contato da cadência — isso já vive na tela de Leads.
        for lead in paciente.leads.all():
            for h in lead.historico.filter(
                tipo__in=[HistoricoLead.Tipo.ENTRADA, HistoricoLead.Tipo.AGENDAMENTO]
            ):
                eventos.append({"data": h.data_hora.date(), "texto": h.descricao})

        # Cobre todos os acompanhamentos já feitos por essa paciente, não só o
        # atual — se ela finalizou um programa e ainda não começou outro, a
        # linha do tempo continua mostrando a jornada completa.
        todos_acompanhamentos = list(paciente.acompanhamentos.all())
        for acomp in todos_acompanhamentos:
            eventos.append({
                "data": acomp.data_inicio,
                "texto": f"Início do acompanhamento — {acomp.programa.nome}",
            })
            if acomp.status_atualizado_em and acomp.status != Acompanhamento.Status.EM_ACOMPANHAMENTO:
                eventos.append({
                    "data": acomp.status_atualizado_em.date(),
                    "texto": f"Acompanhamento — {acomp.get_status_display()}",
                })
            for k in acomp.kits_previstos.all():
                if k.status == k.Status.ENVIADO and k.data_envio:
                    eventos.append({"data": k.data_envio, "texto": f"Kit {k.numero} enviado"})
            for f in FaseModulacao.objects.filter(
                modulacao__acompanhamento=acomp, status=FaseModulacao.Status.CONCLUIDA
            ).select_related("modulacao"):
                eventos.append({
                    "data": f.avaliado_em.date(),
                    "texto": (
                        f"Fase {f.numero} da Modulação {f.modulacao.numero} concluída "
                        f"— {f.get_resultado_display()}"
                    ),
                })

        # Todas as consultas realizadas na Agenda — inclui a de diagnóstico e a
        # de venda (antes do programa existir), não só as previstas no programa.
        numero_por_consulta_id = {}
        for acomp in todos_acompanhamentos:
            numero_por_consulta_id.update({
                cp.consulta_id: cp.numero
                for cp in acomp.consultas_previstas.all()
                if cp.consulta_id
            })
        consultas_realizadas = Consulta.objects.filter(
            organizacao=org, paciente=paciente, status=Consulta.Status.REALIZADA
        ).select_related("tipo_consulta")
        for c in consultas_realizadas:
            if c.pk in numero_por_consulta_id:
                texto = f"Consulta {numero_por_consulta_id[c.pk]} do programa realizada"
            else:
                texto = f"Consulta ({c.tipo_consulta}) realizada"
            eventos.append({"data": c.data_hora.date(), "texto": texto})

        contexto["eventos"] = sorted(eventos, key=lambda e: e["data"])

    if acompanhamento and aba == "geral":
        contexto.update(_financeiro_do_acompanhamento(acompanhamento))

    return render(request, "pacientes/ficha.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
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
