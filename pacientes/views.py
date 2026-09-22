from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

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


# Cada linha do "Resumo visual": chave interna, como calcular a partir de um
# RegistroEvolucao (com inversão quando o campo mede o problema, não o
# bem-estar — ex.: digestao_media mede desconforto, quanto maior pior),
# o campo de satisfação correspondente na anamnese (usado só no ponto
# "Anamnese", o baseline) e a cor da linha no gráfico.
METRICAS_GRAFICO = [
    ("energia", lambda r: r.energia_media, "satisfacao_energia", "#7c5cbf"),
    ("sono", lambda r: r.qualidade_sono, "satisfacao_sono", "#3f9c6d"),
    ("conforto_digestivo", lambda r: None if r.digestao_media is None else 10 - r.digestao_media, "satisfacao_intestino", "#d1a12e"),
    ("pele", lambda r: r.estado_pele, "satisfacao_pele", "#d16b9e"),
    ("emocional", lambda r: r.equilibrio_emocional, "satisfacao_emocional", "#4a90d9"),
    ("hormonal", lambda r: r.equilibrio_hormonal, "satisfacao_hormonal", "#e0793c"),
    ("disposicao", lambda r: r.disposicao_geral, "satisfacao_figado", "#2fa89a"),
]


def _grafico_evolucao(registros, anamnese=None, largura=640, altura=170, margem_esquerda=30, margem=16, margem_baixo=22):
    """
    Coordenadas SVG já prontas pra desenhar as linhas do resumo visual da
    aba Evolução (ver `METRICAS_GRAFICO`) — `registros` deve vir em ordem
    cronológica (mais antigo primeiro).

    Cada data entra no eixo X assim que tiver PELO MENOS UMA das métricas
    calculável, e cada linha só desenha vértice nas datas em que a métrica
    dela específica está disponível — pulando o resto. Isso é de propósito:
    exigir todas as métricas de uma vez faria qualquer check-in antigo
    (de antes de uma métrica nova existir, ou qualquer dia em que a
    paciente pulou uma seção) sumir do gráfico inteiro, não só da linha
    daquela métrica.

    Todas as linhas usam a mesma convenção — quanto mais alto, melhor —,
    por isso `digestao_media` (que mede desconforto: quanto maior, pior)
    entra invertida (10 - valor) como "conforto". Sem isso a linha de
    digestão subiria quando a paciente piorasse, o que é o oposto do que as
    outras linhas mostram.

    Quando `anamnese` tem pelo menos uma nota de satisfação preenchida, ela
    entra como primeiro ponto ("Anamnese", antes de qualquer check-in) —
    dá pra comparar o relato da primeira consulta com a evolução depois
    (só nas linhas cuja nota ela realmente tem). É uma aproximação: a
    anamnese pergunta satisfação (0 a 10) com cada tema, não exatamente a
    mesma métrica calculada do check-in diário — mas segue a mesma escala e
    a mesma convenção (quanto mais alto, melhor), e cada campo de
    satisfação é o mais próximo que a anamnese já tinha do que o check-in
    mede.

    Além das linhas, monta um eixo Y (0 a 10, a régua pedida pra dar
    referência de escala) e um eixo X com a data de cada ponto — esse
    último só quando há poucos pontos, pra não amontoar texto quando o
    histórico tiver muitos check-ins (nesse caso a legenda de período
    embaixo do gráfico já cobre o intervalo).
    """
    pontos = []
    if anamnese is not None:
        valores_anamnese = {
            chave: getattr(anamnese, campo_satisfacao) for chave, _, campo_satisfacao, _ in METRICAS_GRAFICO
        }
        if any(v is not None for v in valores_anamnese.values()):
            pontos.append({"data": anamnese.criado_em, "rotulo": "Anamnese", "valores": valores_anamnese})

    for r in registros:
        valores = {chave: calcular(r) for chave, calcular, _, _ in METRICAS_GRAFICO}
        if any(v is not None for v in valores.values()):
            pontos.append({"data": r.criado_em, "rotulo": None, "valores": valores})

    largura_util = largura - margem_esquerda - margem
    altura_util = altura - 2 * margem - margem_baixo
    n = len(pontos)

    def x_de(i):
        return margem_esquerda if n <= 1 else margem_esquerda + largura_util * i / (n - 1)

    def y_de(valor):
        return margem + altura_util * (1 - valor / 10)

    def linha(chave):
        partes = []
        for i, p in enumerate(pontos):
            valor = p["valores"][chave]
            if valor is not None:
                partes.append(f"{x_de(i):.1f},{y_de(valor):.1f}")
        return " ".join(partes)

    # Formatadas como string (não como float) de propósito: template do
    # Django localiza número solto pro padrão pt-br (vírgula decimal), o
    # que quebraria a coordenada no SVG.
    eixo_y = [{"valor": v, "y": f"{y_de(v):.1f}"} for v in (0, 2, 4, 6, 8, 10)]
    eixo_x = (
        [
            {"data": p["data"], "rotulo": p["rotulo"], "x": f"{x_de(i):.1f}"}
            for i, p in enumerate(pontos)
        ]
        if n <= 6 else []
    )

    return {
        "pontos": pontos,
        "largura": largura,
        "altura": altura,
        "margem_esquerda": margem_esquerda,
        "eixo_y": eixo_y,
        "eixo_x": eixo_x,
        "linhas": [
            {"cor": cor, "points": linha(chave)}
            for chave, _, _, cor in METRICAS_GRAFICO
        ],
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
        anamnese_da_paciente = Anamnese.objects.filter(paciente=paciente).first()
        contexto["grafico_evolucao"] = _grafico_evolucao(list(reversed(registros)), anamnese=anamnese_da_paciente)

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


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
@require_POST
def descartar_fechamento(request, pk):
    """Marca que a paciente decidiu não continuar após a consulta — tira ela da fila de fechamento."""
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=pk, organizacao=org)
    paciente.fechamento_descartado_em = timezone.now()
    paciente.fechamento_descartado_motivo = request.POST.get("motivo", "").strip()
    paciente.save(update_fields=["fechamento_descartado_em", "fechamento_descartado_motivo", "atualizado_em"])
    messages.success(request, "Marcado — essa paciente não aparece mais na fila de fechamento.")
    proximo = request.POST.get("proximo")
    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect("pacientes:ficha", pk=paciente.pk)


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
@require_POST
def reabrir_fechamento(request, pk):
    """Desfaz o 'não vai continuar' — a paciente volta a aparecer na fila de fechamento."""
    org = organizacao_do_usuario(request)
    paciente = get_object_or_404(Paciente, pk=pk, organizacao=org)
    paciente.fechamento_descartado_em = None
    paciente.fechamento_descartado_motivo = ""
    paciente.save(update_fields=["fechamento_descartado_em", "fechamento_descartado_motivo", "atualizado_em"])
    messages.success(request, "Paciente voltou pra fila de fechamento.")
    return redirect("pacientes:ficha", pk=paciente.pk)
