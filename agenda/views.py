import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from contas.utils import organizacao_do_usuario
from financeiro.forms import PagamentoForm, RecebimentoForm
from financeiro.models import Pagamento, Recebimento
from leads.models import Lead, Origem
from pacientes.models import Paciente
from profissionais.models import Profissional

from .forms import BloqueioRapidoForm, ConsultaEditarForm, ConsultaRapidaForm
from .models import Consulta, HorarioBloqueado, TipoConsulta


def _desvincular_consulta_prevista(consulta):
    """Ao cancelar/excluir uma consulta vinculada a uma consulta prevista do programa, devolve o item do checklist pra pendente."""
    from programas.models import ConsultaPrevista

    ConsultaPrevista.objects.filter(consulta=consulta).update(
        consulta=None, status=ConsultaPrevista.Status.PENDENTE_AGENDAMENTO
    )


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

    profissionais = Profissional.objects.filter(organizacao=org, ativo=True).order_by("nome")
    profissional_id = request.GET.get("profissional")
    profissional_selecionado = (
        profissionais.filter(pk=profissional_id).first() if profissional_id else None
    )

    # Colunas exibidas na grade: só a profissional escolhida no filtro, ou
    # todas as profissionais ativas lado a lado ("Agenda geral") — assim dois
    # profissionais podem atender no mesmo horário sem um bloquear o outro.
    colunas_profissionais = [profissional_selecionado] if profissional_selecionado else list(profissionais)

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
    ids_colunas = [prof.pk for prof in colunas_profissionais]
    total_profissionais = len(ids_colunas)

    # células[dia][horario] = lista de itens de qualquer profissional naquele
    # slot — uma coluna só por dia (sem dividir visualmente por profissional),
    # mas dois profissionais ainda podem ter algo no mesmo horário: o card de
    # cada item mostra o responsável, e a célula só para de ser clicável para
    # criar mais um agendamento quando já tem um item por profissional ativo.
    celulas = {dia: {h: [] for h in horarios} for dia in dias}

    for consulta in consultas_qs:
        data_hora_local = timezone.localtime(consulta.data_hora)
        dia = data_hora_local.date()
        if dia in celulas and consulta.profissional_id in ids_colunas:
            slot = _slot_de(horarios, data_hora_local.time())
            celulas[dia][slot].append({"tipo": "consulta", "obj": consulta})

    for bloqueio in bloqueios_qs:
        if bloqueio.profissional_id not in ids_colunas:
            continue
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
            "celulas": [
                {
                    "dia": dia,
                    "itens": celulas[dia][h],
                    "cheia": len(celulas[dia][h]) >= total_profissionais,
                }
                for dia in dias
            ],
        }
        for h in horarios
    ]

    contexto = {
        "dias": dias,
        "linhas": linhas,
        "profissionais": profissionais,
        "profissional_selecionado": profissional_selecionado,
        "tipos_consulta": TipoConsulta.objects.filter(organizacao=org, ativo=True),
        "motivos_bloqueio": HorarioBloqueado.Motivo.choices,
        "origens": Origem.objects.filter(organizacao=org, ativo=True).order_by("nome"),
        "pacientes_json": list(
            Paciente.objects.filter(organizacao=org, ativo=True)
            .order_by("nome")
            .values("id", "nome", "telefone")
        ),
        "intervalo_minutos": org.agenda_intervalo_minutos,
        "intervalo_horas": org.agenda_intervalo_minutos // 60,
        "intervalo_minutos_resto": org.agenda_intervalo_minutos % 60,
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
    horário vazio da grade semanal.
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
    novo_lead = None
    if not paciente:
        paciente = Paciente.objects.create(
            organizacao=org,
            nome=form.cleaned_data["nova_paciente_nome"].strip(),
            telefone=form.cleaned_data.get("nova_paciente_telefone", "").strip(),
        )
        # Agendar direto na Agenda (sem passar pelo CRM primeiro) não pode
        # significar perder a origem do lead nem a comissão de quem agendou
        # — então cria o lead aqui também, já na aba "Agendados".
        novo_lead = Lead.objects.create(
            organizacao=org,
            nome=paciente.nome,
            whatsapp=paciente.telefone,
            origem=form.cleaned_data["origem"],
            responsavel=request.user,
            paciente=paciente,
        )

    consulta = Consulta.objects.create(
        organizacao=org,
        paciente=paciente,
        profissional=form.cleaned_data["profissional"],
        tipo_consulta=form.cleaned_data["tipo_consulta"],
        lead=novo_lead,
        data_hora=data_hora,
        duracao_minutos=form.cleaned_data["duracao_minutos"],
        valor=form.cleaned_data["valor"],
        observacoes=form.cleaned_data["observacoes"],
    )

    if novo_lead:
        novo_lead.marcar_agendada(consulta=consulta, responsavel=request.user)

    # Se a paciente já tem um programa ativo com uma consulta do checklist
    # ainda pendente de agendamento, essa consulta nova já é aquela —
    # vincula automaticamente pra o checklist da ficha refletir sem precisar
    # de nenhum passo extra.
    acompanhamento = paciente.acompanhamento_atual
    if acompanhamento:
        from programas.models import ConsultaPrevista

        prevista = acompanhamento.consultas_previstas.filter(
            status=ConsultaPrevista.Status.PENDENTE_AGENDAMENTO
        ).order_by("numero").first()
        if prevista:
            prevista.consulta = consulta
            prevista.status = ConsultaPrevista.Status.AGENDADA
            prevista.save(update_fields=["consulta", "status"])

    # Como um horário agora pode ter itens de mais de um profissional
    # empilhados na mesma célula, é mais simples recarregar a página do que
    # tentar remendar a célula certa via JS.
    return JsonResponse({"ok": True})


@login_required
@require_POST
def criar_bloqueio_rapido(request):
    """
    Bloqueia um horário (almoço, reunião, folga etc.) a partir do mesmo modal
    de criação rápida da agenda, sem precisar de nenhuma paciente.
    """
    org = organizacao_do_usuario(request)
    form = BloqueioRapidoForm(request.POST, organizacao=org)

    if not form.is_valid():
        return JsonResponse(
            {"ok": False, "errors": form.errors.get_json_data()}, status=400
        )

    inicio = timezone.make_aware(
        datetime.datetime.combine(form.cleaned_data["data"], form.cleaned_data["hora"])
    )
    fim = inicio + datetime.timedelta(minutes=form.cleaned_data["duracao_minutos"])

    HorarioBloqueado.objects.create(
        organizacao=org,
        profissional=form.cleaned_data["profissional"],
        inicio=inicio,
        fim=fim,
        motivo=form.cleaned_data["motivo"],
        observacoes=form.cleaned_data["observacoes"],
    )

    # Um bloqueio pode ocupar vários slots da grade (ex.: 1h de almoço em
    # slots de 30 min) — mais simples e seguro recarregar a página do que
    # tentar remendar cada célula afetada via JS.
    return JsonResponse({"ok": True})


@login_required
@require_POST
def excluir_bloqueio(request, pk):
    """Remove um bloqueio de horário direto da grade da agenda."""
    org = organizacao_do_usuario(request)
    bloqueio = get_object_or_404(HorarioBloqueado, pk=pk, organizacao=org)
    bloqueio.delete()
    return JsonResponse({"ok": True})


@login_required
def detalhe_consulta(request, pk):
    """
    Tela da consulta aberta ao clicar num agendamento já marcado na Agenda.
    Reúne as informações da consulta e o gerenciamento do lançamento
    financeiro vinculado (marcar como pago, editar valor, excluir), sem
    precisar ir até o Financeiro separadamente.
    """
    org = organizacao_do_usuario(request)
    consulta = get_object_or_404(
        Consulta.objects.select_related("paciente", "profissional", "tipo_consulta"),
        pk=pk, organizacao=org,
    )
    pagamento = Pagamento.objects.filter(consulta=consulta, organizacao=org).order_by("-criado_em").first()
    pagamento_form = None
    recebimento_form = None
    consulta_form = None

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "editar_consulta":
            consulta_form = ConsultaEditarForm(request.POST, instance=consulta, organizacao=org, prefix="consulta")
            if consulta_form.is_valid():
                consulta_form.save()  # dispara a sincronização automática do Financeiro (valor/data)
                messages.success(request, "Consulta atualizada.")
                return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "salvar_pagamento" and pagamento:
            pagamento_form = PagamentoForm(request.POST, instance=pagamento)
            if pagamento_form.is_valid():
                pagamento_form.save()
                messages.success(request, "Lançamento atualizado.")
                return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "adicionar_recebimento" and pagamento:
            recebimento_form = RecebimentoForm(request.POST, pagamento=pagamento, prefix="recebimento")
            if recebimento_form.is_valid():
                recebimento = recebimento_form.save(commit=False)
                recebimento.organizacao = org
                recebimento.pagamento = pagamento
                recebimento.save()
                messages.success(request, "Recebimento registrado.")
                return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "excluir_recebimento" and pagamento:
            recebimento = get_object_or_404(
                Recebimento, pk=request.POST.get("recebimento_id"), pagamento=pagamento, organizacao=org
            )
            recebimento.delete()
            messages.success(request, "Recebimento excluído.")
            return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "excluir_pagamento" and pagamento:
            pagamento.delete()
            messages.success(request, "Lançamento excluído.")
            return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "marcar_realizada":
            consulta.status = Consulta.Status.REALIZADA
            consulta.save()
            from programas.models import ConsultaPrevista

            # Cobre tanto a consulta já vinculada na criação (ver
            # criar_consulta_rapida) quanto uma consulta antiga, criada antes
            # dessa vinculação existir — nesse caso vincula agora, à primeira
            # consulta prevista ainda pendente do programa ativo da paciente.
            vinculada = ConsultaPrevista.objects.filter(consulta=consulta).first()
            if vinculada:
                vinculada.status = ConsultaPrevista.Status.REALIZADA
                vinculada.save(update_fields=["status"])
            else:
                acompanhamento = consulta.paciente.acompanhamento_atual
                prevista = acompanhamento.consultas_previstas.filter(
                    status=ConsultaPrevista.Status.PENDENTE_AGENDAMENTO
                ).order_by("numero").first() if acompanhamento else None
                if prevista:
                    prevista.consulta = consulta
                    prevista.status = ConsultaPrevista.Status.REALIZADA
                    prevista.save(update_fields=["consulta", "status"])
            messages.success(request, "Consulta marcada como realizada.")
            return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "cancelar_consulta":
            consulta.status = Consulta.Status.CANCELADA
            consulta.save()  # dispara a sincronização automática do Financeiro
            _desvincular_consulta_prevista(consulta)
            messages.success(
                request,
                "Consulta cancelada. O lançamento pendente vinculado (se houver) também foi cancelado.",
            )
            return redirect("agenda:detalhe_consulta", pk=consulta.pk)

        elif acao == "excluir_consulta":
            _desvincular_consulta_prevista(consulta)
            semana_da_consulta = timezone.localtime(consulta.data_hora).date().isoformat()
            tinha_pagamento = pagamento is not None
            if pagamento:
                pagamento.delete()
            consulta.delete()
            if tinha_pagamento:
                messages.success(request, "Consulta excluída — o lançamento financeiro vinculado também foi removido.")
            else:
                messages.success(request, "Consulta excluída.")
            return redirect(f"{reverse('agenda:semana')}?data={semana_da_consulta}")

    if pagamento and pagamento_form is None:
        pagamento_form = PagamentoForm(instance=pagamento)
    if pagamento and recebimento_form is None:
        recebimento_form = RecebimentoForm(pagamento=pagamento, prefix="recebimento")
    if consulta_form is None:
        consulta_form = ConsultaEditarForm(instance=consulta, organizacao=org, prefix="consulta")

    contexto = {
        "consulta": consulta,
        "pagamento": pagamento,
        "pagamento_form": pagamento_form,
        "recebimento_form": recebimento_form,
        "consulta_form": consulta_form,
        "recebimentos": pagamento.recebimentos.all() if pagamento else [],
        "next": "",
    }
    return render(request, "agenda/detalhe_consulta.html", contexto)


@login_required
@require_POST
def consulta_remover_cobranca(request, pk):
    """
    Tira a cobrança automática de uma consulta que não devia ter valor
    próprio — o caso mais comum é a consulta de diagnóstico que já vira um
    programa fechado, com o mesmo valor do programa duplicado por engano
    (a receita já está contada no tratamento, não deveria contar de novo
    aqui). Zera o valor da consulta, o que já cancela sozinho o lançamento
    pendente vinculado (ver sincronizar_receita_prevista); se já tiver
    dinheiro recebido nela, não mexe — pede pra tirar o recebimento
    primeiro em Gerenciar, pra nunca apagar um valor que já entrou sem
    confirmação explícita.
    """
    org = organizacao_do_usuario(request)
    consulta = get_object_or_404(Consulta.objects.select_related("paciente"), pk=pk, organizacao=org)
    proximo = request.POST.get("next") or ""

    pagamento = Pagamento.objects.filter(consulta=consulta, organizacao=org).exclude(
        status=Pagamento.Status.CANCELADO
    ).first()
    if pagamento and pagamento.total_recebido > 0:
        messages.error(
            request,
            f'Essa consulta de {consulta.paciente} já tem R$ {pagamento.total_recebido:.2f} recebido — '
            'exclua o(s) recebimento(s) em "Gerenciar" antes de remover a cobrança.',
        )
    else:
        consulta.valor = None
        consulta.save(update_fields=["valor", "atualizado_em"])
        messages.success(request, f"Cobrança removida da consulta de {consulta.paciente}.")

    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect("agenda:detalhe_consulta", pk=consulta.pk)
