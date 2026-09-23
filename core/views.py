import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from agenda.models import Consulta
from contas.models import Usuario
from contas.utils import organizacao_do_usuario, usuario_e_administrador
from financeiro.models import Pagamento
from financeiro.views import totais_fechamentos_mes
from leads.forms import RegistroSocialSellingForm
from leads.models import HistoricoLead, Lead, RegistroSocialSelling
from pacientes.models import Paciente
from programas.models import Acompanhamento

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

    limite_parado = timezone.now() - datetime.timedelta(days=org.dias_lead_parado)
    leads_parados = leads_ativos.filter(atualizado_em__lte=limite_parado).order_by("atualizado_em")

    alertas_acompanhamentos = []
    for acomp in Acompanhamento.objects.filter(
        organizacao=org, status__in=Acompanhamento.STATUS_ATIVOS
    ).select_related("paciente"):
        for alerta in acomp.alertas():
            alertas_acompanhamentos.append({"acompanhamento": acomp, "texto": alerta})

    contexto = {
        "org": org,
        "usuario_e_administrador": usuario_e_administrador(request),
        "novos_hoje": leads_ativos.filter(etapa=Lead.Etapa.NOVO, entrou_em__date=hoje).count(),
        "contato_1": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_1).count(),
        "contato_2": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_2).count(),
        "contato_3": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_3).count(),
        "contato_4": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_4).count(),
        "retomar_hoje": leads_pausados_hoje.count(),
        "atrasados": [lead for lead in leads_ativos if lead.esta_atrasado],
        "leads_parados": [
            {"lead": lead, "dias": (hoje - timezone.localtime(lead.atualizado_em).date()).days}
            for lead in leads_parados[:12]
        ],
        "total_leads_parados": leads_parados.count(),
        "dias_lead_parado": org.dias_lead_parado,
        "fila": fila[:12],
        "alertas_acompanhamentos": alertas_acompanhamentos[:10],
        "consultas_hoje": Consulta.objects.filter(
            organizacao=org, data_hora__gte=inicio_hoje, data_hora__lt=fim_hoje
        ).exclude(status=Consulta.Status.CANCELADA).select_related(
            "paciente", "profissional", "tipo_consulta"
        ).order_by("data_hora"),
        "pagamentos_pendentes": Pagamento.objects.filter(
            organizacao=org, status=Pagamento.Status.PENDENTE
        ).order_by("data_vencimento")[:10],
    }

    if org.modulo_financeiro_ativo and request.user.papel != Usuario.Papel.COMERCIAL:
        totais_mes_atual = totais_fechamentos_mes(org, hoje.year, hoje.month)
        faltam_faturamento = max(org.meta_faturamento_mensal - totais_mes_atual["total_geral"], Decimal("0.00"))
        faltam_consultas = max(org.meta_consultas_mensal - totais_mes_atual["qtd_consultas"], 0)
        faltam_fechamentos = max(org.meta_fechamentos_mensal - totais_mes_atual["qtd_tratamentos"], 0)
        contexto["meta_mes"] = {
            "meta_faturamento": org.meta_faturamento_mensal,
            "faturado": totais_mes_atual["total_geral"],
            "faltam_faturamento": faltam_faturamento,
            "percentual_faturamento": min(
                round(totais_mes_atual["total_geral"] / org.meta_faturamento_mensal * 100) if org.meta_faturamento_mensal else 0,
                100,
            ),
            "meta_consultas": org.meta_consultas_mensal,
            "qtd_consultas": totais_mes_atual["qtd_consultas"],
            "faltam_consultas": faltam_consultas,
            "meta_fechamentos": org.meta_fechamentos_mensal,
            "qtd_fechamentos": totais_mes_atual["qtd_tratamentos"],
            "faltam_fechamentos": faltam_fechamentos,
        }

    if org.modulo_programas_ativo and request.user.papel != Usuario.Papel.COMERCIAL:
        pacientes_candidatas = Paciente.objects.filter(
            organizacao=org,
            consultas__status=Consulta.Status.REALIZADA,
            consultas__tipo_consulta__conta_para_fechamento=True,
            fechamento_descartado_em__isnull=True,
        ).exclude(
            acompanhamentos__status__in=Acompanhamento.STATUS_ATIVOS
        ).distinct()
        fila_fechamento = []
        for paciente in pacientes_candidatas:
            ultima_consulta = paciente.consultas.filter(
                status=Consulta.Status.REALIZADA, tipo_consulta__conta_para_fechamento=True
            ).select_related("profissional", "tipo_consulta").order_by("-data_hora").first()
            if ultima_consulta:
                fila_fechamento.append({"paciente": paciente, "consulta": ultima_consulta})
        fila_fechamento.sort(key=lambda item: item["consulta"].data_hora, reverse=True)
        contexto["fila_fechamento"] = fila_fechamento[:20]
        contexto["total_fila_fechamento"] = len(fila_fechamento)

    if request.user.papel == Usuario.Papel.COMERCIAL:
        agendamentos_mes = HistoricoLead.objects.filter(
            lead__organizacao=org,
            tipo=HistoricoLead.Tipo.AGENDAMENTO,
            responsavel=request.user,
            data_hora__year=hoje.year,
            data_hora__month=hoje.month,
        ).count()
        comissao_agendamentos = agendamentos_mes * request.user.comissao_por_agendamento
        contexto["remuneracao"] = {
            "fixo_mensal": request.user.comissao_fixo_mensal,
            "valor_por_agendamento": request.user.comissao_por_agendamento,
            "agendamentos_mes": agendamentos_mes,
            "comissao_agendamentos": comissao_agendamentos,
            "total_mes": request.user.comissao_fixo_mensal + comissao_agendamentos,
        }
        registro_hoje = RegistroSocialSelling.objects.filter(
            organizacao=org, usuario=request.user, data=hoje,
        ).first()
        contexto["form_social_selling"] = RegistroSocialSellingForm(instance=registro_hoje)
    else:
        campos_social = ["seguidores_novos", "pessoas_chamadas", "pessoas_responderam", "contatos_conseguidos"]
        registros_hoje = {
            r.usuario_id: r for r in RegistroSocialSelling.objects.filter(organizacao=org, data=hoje)
        }
        totais_mes = {
            r["usuario_id"]: r for r in RegistroSocialSelling.objects.filter(
                organizacao=org, data__year=hoje.year, data__month=hoje.month,
            ).values("usuario_id").annotate(**{campo: Sum(campo) for campo in campos_social})
        }
        equipe_social = [
            {
                "usuario": sdr,
                "hoje": registros_hoje.get(sdr.pk),
                "mes": totais_mes.get(sdr.pk),
            }
            for sdr in Usuario.objects.filter(organizacao=org, papel=Usuario.Papel.COMERCIAL, is_active=True)
        ]
        if equipe_social:
            contexto["equipe_social_selling"] = equipe_social

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
