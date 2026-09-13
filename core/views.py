import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from agenda.models import Consulta
from contas.utils import organizacao_do_usuario
from financeiro.models import Pagamento
from leads.models import Lead

BADGE_POR_ETAPA = {
    Lead.Etapa.NOVO: "1º contato",
    Lead.Etapa.CONTATO_1: "1º contato",
    Lead.Etapa.CONTATO_2: "2º contato",
    Lead.Etapa.CONTATO_3: "3º contato — prova social",
    Lead.Etapa.CONTATO_4: "4º contato — encerramento",
}


def _linha_da_fila(lead, hoje):
    pausa = lead.pausa_ativa
    if pausa and pausa.data_retomada_prevista <= hoje:
        subtitulo = (
            "Pediu para ser chamada(o) hoje" if pausa.data_retomada_prevista == hoje
            else "Retomada de cadência atrasada"
        )
        return {"lead": lead, "badge": "Retomar cadência", "subtitulo": subtitulo}

    if lead.etapa == Lead.Etapa.NOVO:
        entrada_local = timezone.localtime(lead.entrou_em)
        if entrada_local.date() == hoje:
            subtitulo = f"Entrou hoje às {entrada_local:%H:%M}"
        else:
            subtitulo = f"Entrou em {entrada_local:%d/%m}"
    elif lead.ultimo_contato_em:
        dias = (hoje - timezone.localtime(lead.ultimo_contato_em).date()).days
        if dias <= 0:
            subtitulo = "Contato feito hoje"
        elif dias == 1:
            subtitulo = "Último contato ontem"
        else:
            subtitulo = f"Sem resposta há {dias} dias"
    else:
        subtitulo = "Aguardando contato"

    return {
        "lead": lead,
        "badge": BADGE_POR_ETAPA.get(lead.etapa, lead.get_etapa_display()),
        "subtitulo": subtitulo,
    }


@login_required
def home(request):
    org = organizacao_do_usuario(request)
    hoje = timezone.localdate()
    inicio_hoje = timezone.make_aware(datetime.datetime.combine(hoje, datetime.time.min))
    fim_hoje = inicio_hoje + datetime.timedelta(days=1)

    leads_ativos = Lead.objects.filter(
        organizacao=org, status__in=[Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO]
    ).select_related("origem")
    leads_pausados_hoje = Lead.objects.filter(
        organizacao=org, status=Lead.Status.PAUSADO,
        pausas__retomado_em__isnull=True,
        pausas__data_retomada_prevista__lte=hoje,
    ).select_related("origem").distinct()

    fila = sorted(
        [_linha_da_fila(lead, hoje) for lead in list(leads_ativos) + list(leads_pausados_hoje)],
        key=lambda item: item["lead"].entrou_em,
    )

    contexto = {
        "novos_hoje": leads_ativos.filter(etapa=Lead.Etapa.NOVO, entrou_em__date=hoje).count(),
        "contato_1": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_1).count(),
        "contato_2": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_2).count(),
        "contato_3": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_3).count(),
        "contato_4": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_4).count(),
        "retomar_hoje": leads_pausados_hoje.count(),
        "atrasados": [lead for lead in leads_ativos if lead.esta_atrasado],
        "fila": fila[:12],
        "consultas_hoje": Consulta.objects.filter(
            organizacao=org, data_hora__gte=inicio_hoje, data_hora__lt=fim_hoje
        ).exclude(status=Consulta.Status.CANCELADA).select_related(
            "paciente", "profissional", "tipo_consulta"
        ).order_by("data_hora"),
        "pagamentos_pendentes": Pagamento.objects.filter(
            organizacao=org, status=Pagamento.Status.PENDENTE
        ).order_by("data_vencimento")[:10],
    }
    return render(request, "core/home.html", contexto)


@login_required
def indicadores(request):
    org = organizacao_do_usuario(request)

    leads_qs = Lead.objects.filter(organizacao=org)
    por_status = leads_qs.values("status").annotate(total=Count("id")).order_by("-total")
    por_origem = leads_qs.values("origem__nome").annotate(total=Count("id")).order_by("-total")
    por_motivo_perda = (
        leads_qs.filter(status=Lead.Status.PERDIDA, perdido_motivo__isnull=False)
        .values("perdido_motivo__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    consultas_por_status = (
        Consulta.objects.filter(organizacao=org)
        .values("status")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    status_labels = dict(Lead.Status.choices)

    contexto = {
        "total_leads": leads_qs.count(),
        "por_status": [
            {"label": status_labels.get(r["status"], r["status"]), "total": r["total"]}
            for r in por_status
        ],
        "por_origem": por_origem,
        "por_motivo_perda": por_motivo_perda,
        "consultas_por_status": [
            {"label": dict(Consulta.Status.choices).get(r["status"], r["status"]), "total": r["total"]}
            for r in consultas_por_status
        ],
    }
    return render(request, "core/indicadores.html", contexto)


@login_required
def em_breve(request, modulo):
    return render(request, "core/em_breve.html", {"modulo": modulo})
