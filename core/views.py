import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from agenda.models import Consulta
from contas.utils import organizacao_do_usuario
from financeiro.models import Pagamento
from leads.models import Lead
from pacientes.models import Paciente


@login_required
def home(request):
    org = organizacao_do_usuario(request)
    hoje = timezone.localdate()
    agora = timezone.now()
    inicio_hoje = timezone.make_aware(datetime.datetime.combine(hoje, datetime.time.min))
    fim_hoje = inicio_hoje + datetime.timedelta(days=1)

    leads_ativos = Lead.objects.filter(
        organizacao=org, status__in=[Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO]
    )

    contexto = {
        "novos_hoje": leads_ativos.filter(etapa=Lead.Etapa.NOVO, entrou_em__date=hoje).count(),
        "contato_1": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_1).count(),
        "contato_2": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_2).count(),
        "contato_3": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_3).count(),
        "contato_4": leads_ativos.filter(etapa=Lead.Etapa.CONTATO_4).count(),
        "retomar_hoje": Lead.objects.filter(
            organizacao=org, status=Lead.Status.PAUSADO,
            pausas__retomado_em__isnull=True,
            pausas__data_retomada_prevista__lte=hoje,
        ).distinct().count(),
        "atrasados": [lead for lead in leads_ativos if lead.esta_atrasado],
        "total_pacientes_ativos": Paciente.objects.filter(organizacao=org, ativo=True).count(),
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
