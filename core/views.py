from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from agenda.models import Consulta
from financeiro.models import Pagamento
from pacientes.models import Paciente


def home(request):
    hoje = timezone.localdate()
    inicio_hoje = timezone.make_aware(
        timezone.datetime.combine(hoje, timezone.datetime.min.time())
    )
    fim_hoje = inicio_hoje + timedelta(days=1)

    contexto = {
        "total_pacientes_ativos": Paciente.objects.filter(ativo=True).count(),
        "consultas_hoje": Consulta.objects.filter(
            data_hora__gte=inicio_hoje, data_hora__lt=fim_hoje
        ).exclude(status=Consulta.Status.CANCELADA).order_by("data_hora"),
        "proximas_consultas": Consulta.objects.filter(
            data_hora__gte=fim_hoje,
            status__in=[Consulta.Status.AGENDADA, Consulta.Status.CONFIRMADA],
        ).order_by("data_hora")[:10],
        "pagamentos_pendentes": Pagamento.objects.filter(
            status=Pagamento.Status.PENDENTE
        ).order_by("data_vencimento")[:10],
    }
    return render(request, "core/home.html", contexto)
