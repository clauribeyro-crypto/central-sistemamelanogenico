import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from agenda.models import Consulta
from contas.models import Organizacao, Usuario
from contas.utils import organizacao_do_usuario, usuario_e_administrador
from estoque.models import Venda
from financeiro.models import Pagamento
from financeiro.views import MESES, totais_fechamentos_mes
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

    if request.user.papel != Usuario.Papel.COMERCIAL:
        # Valor de produtos vendidos hoje — só pra dar uma visão do dia aqui
        # na home, sem entrar na meta do mês (que é só de tratamento/consulta).
        vendas_hoje = list(Venda.objects.filter(organizacao=org, data=hoje).prefetch_related("itens"))
        contexto["qtd_vendas_produtos_hoje"] = len(vendas_hoje)
        contexto["valor_vendas_produtos_hoje"] = sum((v.valor_total for v in vendas_hoje), Decimal("0.00"))

    if org.modulo_financeiro_ativo and request.user.papel != Usuario.Papel.COMERCIAL:
        totais_mes_atual = totais_fechamentos_mes(org, hoje.year, hoje.month)
        # A meta é sobre dinheiro em caixa, não sobre valor fechado/contratado —
        # tratamento ou consulta com saldo a receber não entra até ser pago.
        faturado = totais_mes_atual["total_recebido_geral"]
        qtd_fechamentos_pagos = sum(1 for t in totais_mes_atual["tratamentos"] if t.total_recebido > 0)
        qtd_consultas_pagas = sum(1 for c in totais_mes_atual["consultas"] if c.total_recebido > 0)
        faltam_faturamento = max(org.meta_faturamento_mensal - faturado, Decimal("0.00"))
        faltam_consultas = max(org.meta_consultas_mensal - qtd_consultas_pagas, 0)
        faltam_fechamentos = max(org.meta_fechamentos_mensal - qtd_fechamentos_pagos, 0)
        contexto["meta_mes"] = {
            "meta_faturamento": org.meta_faturamento_mensal,
            "faturado": faturado,
            "faltam_faturamento": faltam_faturamento,
            "percentual_faturamento": min(
                round(faturado / org.meta_faturamento_mensal * 100) if org.meta_faturamento_mensal else 0,
                100,
            ),
            "meta_consultas": org.meta_consultas_mensal,
            "qtd_consultas": qtd_consultas_pagas,
            "faltam_consultas": faltam_consultas,
            "meta_fechamentos": org.meta_fechamentos_mensal,
            "qtd_fechamentos": qtd_fechamentos_pagos,
            "faltam_fechamentos": faltam_fechamentos,
        }

    if org.modulo_programas_ativo and request.user.papel != Usuario.Papel.COMERCIAL:
        contexto["total_fila_fechamento"] = Paciente.objects.filter(
            organizacao=org,
            consultas__status=Consulta.Status.REALIZADA,
            consultas__tipo_consulta__conta_para_fechamento=True,
            fechamento_descartado_em__isnull=True,
        ).exclude(
            acompanhamentos__status__in=Acompanhamento.STATUS_ATIVOS
        ).distinct().count()

    if request.user.papel == Usuario.Papel.COMERCIAL:
        # .distinct("lead_id") em vez de .count() direto: se a mesma lead for
        # reagendada mais de uma vez no mês (ex.: a consulta foi excluída por
        # engano e recriada), só a primeira agendada conta comissão — senão
        # corrigir um agendamento vira comissão em dobro pela mesma lead.
        agendamentos_mes = HistoricoLead.objects.filter(
            lead__organizacao=org,
            tipo=HistoricoLead.Tipo.AGENDAMENTO,
            responsavel=request.user,
            data_hora__year=hoje.year,
            data_hora__month=hoje.month,
        ).values("lead_id").distinct().count()
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
def painel_mentoradas(request):
    """
    Visão geral só pra administradora geral (mentora) — os números
    principais de cada clínica mentorada lado a lado, sem precisar entrar
    organização por organização nem vasculhar o /admin/ bruto.
    """
    if not request.user.is_superuser:
        messages.error(request, "Só a administradora geral pode ver o painel de mentoradas.")
        return redirect("core:home")

    hoje = timezone.localdate()
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

    clinicas = []
    for org in Organizacao.objects.filter(ativo=True).order_by("nome"):
        totais = totais_fechamentos_mes(org, ano, mes)
        faturado = totais["total_recebido_geral"]
        meta = org.meta_faturamento_mensal
        clinicas.append({
            "org": org,
            "faturado": faturado,
            "meta": meta,
            "percentual_meta": min(round(faturado / meta * 100) if meta else 0, 100),
            "qtd_consultas": totais["qtd_consultas"],
            "meta_consultas": org.meta_consultas_mensal,
            "qtd_fechamentos": totais["qtd_tratamentos"],
            "meta_fechamentos": org.meta_fechamentos_mensal,
        })

    contexto = {
        "ano": ano,
        "mes": mes,
        "mes_nome": dict(MESES)[mes],
        "meses": MESES,
        "anos": range(hoje.year - 3, hoje.year + 2),
        "clinicas": clinicas,
    }
    return render(request, "core/painel_mentoradas.html", contexto)


@login_required
def em_breve(request, modulo):
    return render(request, "core/em_breve.html", {"modulo": modulo})
