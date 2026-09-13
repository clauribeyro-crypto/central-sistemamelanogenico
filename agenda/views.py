import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from contas.utils import organizacao_do_usuario
from profissionais.models import Profissional

from .models import Consulta, HorarioBloqueado, TipoConsulta


def _horarios_do_dia(org):
    passo = datetime.timedelta(minutes=org.agenda_intervalo_minutos)
    base = datetime.date.today()
    atual = datetime.datetime.combine(base, org.agenda_hora_inicio)
    fim = datetime.datetime.combine(base, org.agenda_hora_fim)
    horarios = []
    while atual < fim:
        horarios.append(atual.time())
        atual += passo
    return horarios


def _slot_de(horarios, hora):
    slot = horarios[0]
    for h in horarios:
        if h <= hora:
            slot = h
        else:
            break
    return slot


@login_required
def semana(request):
    org = organizacao_do_usuario(request)

    data_param = request.GET.get("data")
    referencia = (
        datetime.date.fromisoformat(data_param) if data_param else datetime.date.today()
    )
    inicio_semana = referencia - datetime.timedelta(days=referencia.weekday())
    dias = [inicio_semana + datetime.timedelta(days=i) for i in range(7)]  # segunda a domingo

    profissionais = Profissional.objects.filter(organizacao=org, ativo=True)
    profissional_id = request.GET.get("profissional")
    profissional_selecionado = (
        profissionais.filter(pk=profissional_id).first() if profissional_id else None
    )

    consultas_qs = (
        Consulta.objects.filter(
            organizacao=org, data_hora__date__gte=dias[0], data_hora__date__lte=dias[-1]
        )
        .exclude(status=Consulta.Status.CANCELADA)
        .select_related("paciente", "profissional", "tipo_consulta")
    )
    bloqueios_qs = HorarioBloqueado.objects.filter(
        organizacao=org, inicio__date__lte=dias[-1], fim__date__gte=dias[0]
    ).select_related("profissional")

    if profissional_selecionado:
        consultas_qs = consultas_qs.filter(profissional=profissional_selecionado)
        bloqueios_qs = bloqueios_qs.filter(profissional=profissional_selecionado)

    horarios = _horarios_do_dia(org)

    # células[dia][horario] = lista de itens (consultas/bloqueios) daquele slot
    celulas = {dia: {h: [] for h in horarios} for dia in dias}

    for consulta in consultas_qs:
        dia = consulta.data_hora.date()
        if dia in celulas:
            slot = _slot_de(horarios, consulta.data_hora.time())
            celulas[dia][slot].append({"tipo": "consulta", "obj": consulta})

    for bloqueio in bloqueios_qs:
        dia_atual = max(bloqueio.inicio.date(), dias[0])
        dia_fim = min(bloqueio.fim.date(), dias[-1])
        while dia_atual <= dia_fim:
            if dia_atual in celulas:
                hora_ini = bloqueio.inicio.time() if bloqueio.inicio.date() == dia_atual else horarios[0]
                hora_fim = bloqueio.fim.time() if bloqueio.fim.date() == dia_atual else horarios[-1]
                for h in horarios:
                    if hora_ini <= h < hora_fim:
                        celulas[dia_atual][h].append({"tipo": "bloqueio", "obj": bloqueio})
            dia_atual += datetime.timedelta(days=1)

    linhas = [
        {"horario": h, "celulas": [celulas[dia][h] for dia in dias]}
        for h in horarios
    ]

    contexto = {
        "dias": dias,
        "linhas": linhas,
        "profissionais": profissionais,
        "profissional_selecionado": profissional_selecionado,
        "tipos_consulta": TipoConsulta.objects.filter(organizacao=org, ativo=True),
        "semana_anterior": (inicio_semana - datetime.timedelta(days=7)).isoformat(),
        "semana_seguinte": (inicio_semana + datetime.timedelta(days=7)).isoformat(),
        "hoje": datetime.date.today(),
    }
    return render(request, "agenda/semana.html", contexto)
