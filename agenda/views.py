import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario
from pacientes.models import Paciente
from profissionais.models import Profissional

from .forms import ConsultaRapidaForm
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
        data_hora_local = timezone.localtime(consulta.data_hora)
        dia = data_hora_local.date()
        if dia in celulas:
            slot = _slot_de(horarios, data_hora_local.time())
            celulas[dia][slot].append({"tipo": "consulta", "obj": consulta})

    for bloqueio in bloqueios_qs:
        inicio_local = timezone.localtime(bloqueio.inicio)
        fim_local = timezone.localtime(bloqueio.fim)
        dia_atual = max(inicio_local.date(), dias[0])
        dia_fim = min(fim_local.date(), dias[-1])
        while dia_atual <= dia_fim:
            if dia_atual in celulas:
                hora_ini = inicio_local.time() if inicio_local.date() == dia_atual else horarios[0]
                hora_fim = fim_local.time() if fim_local.date() == dia_atual else horarios[-1]
                for h in horarios:
                    if hora_ini <= h < hora_fim:
                        celulas[dia_atual][h].append({"tipo": "bloqueio", "obj": bloqueio})
            dia_atual += datetime.timedelta(days=1)

    linhas = [
        {
            "horario": h,
            "celulas": [{"dia": dia, "itens": celulas[dia][h]} for dia in dias],
        }
        for h in horarios
    ]

    contexto = {
        "dias": dias,
        "linhas": linhas,
        "profissionais": profissionais,
        "profissional_selecionado": profissional_selecionado,
        "tipos_consulta": TipoConsulta.objects.filter(organizacao=org, ativo=True),
        "pacientes_json": list(
            Paciente.objects.filter(organizacao=org, ativo=True)
            .order_by("nome")
            .values("id", "nome", "telefone")
        ),
        "intervalo_minutos": org.agenda_intervalo_minutos,
        "semana_anterior": (inicio_semana - datetime.timedelta(days=7)).isoformat(),
        "semana_seguinte": (inicio_semana + datetime.timedelta(days=7)).isoformat(),
        "hoje": datetime.date.today(),
    }
    return render(request, "agenda/semana.html", contexto)


@login_required
@require_POST
def criar_consulta_rapida(request):
    """
    Cria uma consulta a partir do formulário rápido aberto ao clicar num
    horário vazio da grade semanal. Responde em JSON para a página atualizar
    a célula sem recarregar.
    """
    org = organizacao_do_usuario(request)
    form = ConsultaRapidaForm(request.POST, organizacao=org)

    if not form.is_valid():
        return JsonResponse(
            {"ok": False, "errors": form.errors.get_json_data()}, status=400
        )

    data_hora = timezone.make_aware(
        datetime.datetime.combine(form.cleaned_data["data"], form.cleaned_data["hora"])
    )

    paciente = form.cleaned_data["paciente"]
    if not paciente:
        paciente = Paciente.objects.create(
            organizacao=org,
            nome=form.cleaned_data["nova_paciente_nome"].strip(),
            telefone=form.cleaned_data.get("nova_paciente_telefone", "").strip(),
        )

    consulta = Consulta.objects.create(
        organizacao=org,
        paciente=paciente,
        profissional=form.cleaned_data["profissional"],
        tipo_consulta=form.cleaned_data["tipo_consulta"],
        data_hora=data_hora,
        duracao_minutos=form.cleaned_data["duracao_minutos"],
        observacoes=form.cleaned_data["observacoes"],
    )

    data_hora_local = timezone.localtime(consulta.data_hora)
    html = render_to_string(
        "agenda/_bloco_consulta.html", {"consulta": consulta}, request=request
    )
    return JsonResponse({
        "ok": True,
        "html": html,
        "dia": data_hora_local.date().isoformat(),
        "horario": _slot_de(_horarios_do_dia(org), data_hora_local.time()).strftime("%H:%M"),
    })
