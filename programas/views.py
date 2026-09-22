import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from agenda.models import Consulta, TipoConsulta
from contas.utils import modulo_ativo_obrigatorio, organizacao_do_usuario, usuario_e_administrador
from estoque.models import Produto, Recompra
from financeiro.models import Pagamento

from .forms import (
    AcompanhamentoForm,
    AvaliacaoFaseForm,
    FeedbackForm,
    FotoEvolucaoForm,
    PlanoFaseForm,
    ProgramaForm,
    TipoConsultaForm,
)
from .models import (
    Acompanhamento, ConsultaPrevista, Feedback, FaseModulacao, FotoEvolucao, KitPrevisto, KitProdutoItem, Programa,
)


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def configuracoes(request):
    org = organizacao_do_usuario(request)
    aba = request.GET.get("aba", "tipos")
    if aba not in ("tipos", "planos"):
        aba = "tipos"

    contexto = {
        "aba_atual": aba,
        "tipos_consulta": TipoConsulta.objects.filter(organizacao=org).order_by("ordem", "nome"),
        "programas": Programa.objects.filter(organizacao=org).order_by("duracao_meses"),
    }
    return render(request, "programas/configuracoes.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def tipo_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = TipoConsultaForm(request.POST)
        if form.is_valid():
            tipo = form.save(commit=False)
            tipo.organizacao = org
            tipo.save()
            messages.success(request, "Tipo de consulta cadastrado.")
            return redirect("programas:configuracoes")
    else:
        form = TipoConsultaForm()
    return render(request, "programas/tipo_form.html", {"form": form, "tipo": None})


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def tipo_editar(request, pk):
    org = organizacao_do_usuario(request)
    tipo = get_object_or_404(TipoConsulta, pk=pk, organizacao=org)
    if request.method == "POST":
        form = TipoConsultaForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de consulta atualizado.")
            return redirect("programas:configuracoes")
    else:
        form = TipoConsultaForm(instance=tipo)
    return render(request, "programas/tipo_form.html", {"form": form, "tipo": tipo})


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def plano_criar(request):
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = ProgramaForm(request.POST)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.organizacao = org
            plano.save()
            messages.success(request, "Plano de acompanhamento cadastrado.")
            return redirect("programas:configuracoes")
    else:
        form = ProgramaForm()
    return render(request, "programas/plano_form.html", {"form": form, "plano": None})


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def plano_editar(request, pk):
    org = organizacao_do_usuario(request)
    plano = get_object_or_404(Programa, pk=pk, organizacao=org)
    if request.method == "POST":
        form = ProgramaForm(request.POST, instance=plano)
        if form.is_valid():
            form.save()
            messages.success(request, "Plano de acompanhamento atualizado.")
            return redirect("programas:configuracoes")
    else:
        form = ProgramaForm(instance=plano)
    return render(request, "programas/plano_form.html", {"form": form, "plano": plano})


ACOES_STATUS = {
    "finalizar": (Acompanhamento.Status.FINALIZADO, "Acompanhamento finalizado."),
    "manutencao": (Acompanhamento.Status.MANUTENCAO, "Acompanhamento movido para manutenção."),
    "aguardando_decisao": (
        Acompanhamento.Status.AGUARDANDO_DECISAO,
        "Acompanhamento marcado como aguardando decisão da paciente.",
    ),
    "renovar": (Acompanhamento.Status.RENOVADO, "Acompanhamento marcado como renovado."),
    "migrar": (Acompanhamento.Status.MIGRADO, "Acompanhamento marcado como migrado para outro programa."),
}


@login_required
@require_POST
def mudar_status_acompanhamento(request, pk):
    """
    Ações de fim/continuidade de programa (Doc 1 §11): finalizar, colocar em
    manutenção, marcar aguardando decisão, ou renovar/migrar — nesses dois
    últimos casos, encerra o acompanhamento atual com o status certo e manda
    direto pra tela de iniciar um novo (mesma paciente, sem cadastro novo,
    o histórico do acompanhamento anterior continua na ficha).
    """
    org = organizacao_do_usuario(request)
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    acao = request.POST.get("acao")
    if acao not in ACOES_STATUS:
        messages.error(request, "Ação inválida.")
        return redirect("pacientes:ficha", pk=acompanhamento.paciente.pk)

    novo_status, mensagem = ACOES_STATUS[acao]
    acompanhamento.status = novo_status
    acompanhamento.status_atualizado_em = timezone.now()
    acompanhamento.save(update_fields=["status", "status_atualizado_em"])
    messages.success(request, mensagem)

    if acao in ("renovar", "migrar"):
        return redirect("pacientes:iniciar_protocolo", pk=acompanhamento.paciente.pk)
    return redirect("pacientes:ficha", pk=acompanhamento.paciente.pk)


@login_required
@modulo_ativo_obrigatorio("modulo_programas_ativo", "Programas/Acompanhamento")
def acompanhamento_editar(request, pk):
    """
    Corrige valor/desconto/forma de pagamento/data de início de um
    tratamento já fechado — pra quando o lançamento foi feito errado (ex.:
    valor digitado errado). Programa e status ficam de fora (ver
    AcompanhamentoForm) — pra isso existem os fluxos próprios.
    """
    org = organizacao_do_usuario(request)
    if not usuario_e_administrador(request):
        messages.error(request, "Só administradores podem editar tratamentos fechados.")
        return redirect("pacientes:lista")
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente", "programa"), pk=pk, organizacao=org
    )
    proximo = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = AcompanhamentoForm(request.POST, instance=acompanhamento)
        if form.is_valid():
            acompanhamento = form.save(commit=False)
            acompanhamento.data_termino_prevista = acompanhamento.data_inicio + datetime.timedelta(
                days=30 * acompanhamento.programa.duracao_meses
            )
            acompanhamento.save()

            pagamento = acompanhamento.pagamentos.exclude(status=Pagamento.Status.CANCELADO).first()
            if pagamento:
                pagamento.valor = acompanhamento.valor_contratado - acompanhamento.desconto
                pagamento.save(update_fields=["valor", "atualizado_em"])
                pagamento.recalcular_status()

            messages.success(request, "Tratamento atualizado.")
            if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
                return redirect(proximo)
            return redirect("pacientes:ficha", pk=acompanhamento.paciente.pk)
    else:
        # Se o valor do pagamento foi corrigido direto no Financeiro (sem
        # passar por essa tela), reconcilia aqui antes de mostrar o
        # formulário — senão reabriria mostrando o valor antigo de novo.
        pagamento = acompanhamento.pagamentos.exclude(status=Pagamento.Status.CANCELADO).first()
        if pagamento and pagamento.valor != acompanhamento.valor_contratado - acompanhamento.desconto:
            acompanhamento.valor_contratado = pagamento.valor + acompanhamento.desconto
        form = AcompanhamentoForm(instance=acompanhamento)

    contexto = {"form": form, "acompanhamento": acompanhamento, "next": proximo}
    return render(request, "programas/acompanhamento_form.html", contexto)


@login_required
@require_POST
def acompanhamento_excluir(request, pk):
    """
    Exclui um tratamento fechado por engano — ex.: "Iniciar protocolo"
    clicado duas vezes, deixando um programa vazio duplicado. Só permite
    quando não tem dinheiro recebido nele, mesmo motivo do "Remover
    cobrança" das consultas: nunca apagar valor que já entrou sem uma ação
    separada e explícita. Some junto o(s) pagamento(s) vinculados (o
    acompanhamento em si não os apaga sozinho — a FK é SET_NULL).
    """
    org = organizacao_do_usuario(request)
    if not usuario_e_administrador(request):
        messages.error(request, "Só administradores podem excluir tratamentos.")
        return redirect("pacientes:lista")
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=pk, organizacao=org
    )
    proximo = request.POST.get("next") or ""
    paciente_pk = acompanhamento.paciente.pk

    pagamentos = acompanhamento.pagamentos.exclude(status=Pagamento.Status.CANCELADO)
    total_recebido = sum((p.total_recebido for p in pagamentos), Decimal("0.00"))
    if total_recebido > 0:
        messages.error(
            request,
            f'O tratamento de {acompanhamento.paciente} já tem R$ {total_recebido:.2f} recebido — '
            'exclua o(s) recebimento(s) em "Gerenciar" antes de excluir o tratamento.',
        )
    else:
        nome = str(acompanhamento.paciente)
        pagamentos.delete()
        acompanhamento.delete()
        messages.success(request, f"Tratamento de {nome} excluído.")

    if proximo and url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
        return redirect(proximo)
    return redirect("pacientes:ficha", pk=paciente_pk)


@login_required
@require_POST
def vincular_consulta_prevista(request, pk):
    """
    Liga uma consulta que já aconteceu (ex.: a consulta de diagnóstico,
    agendada antes do protocolo existir) a um item do checklist do
    programa — pra parar de pedir "agendar a Consulta N" quando ela já
    ocorreu, sem precisar mexer no admin.
    """
    org = organizacao_do_usuario(request)
    consulta_prevista = get_object_or_404(
        ConsultaPrevista.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    paciente = consulta_prevista.acompanhamento.paciente
    consulta = get_object_or_404(Consulta, pk=request.POST.get("consulta_id"), organizacao=org, paciente=paciente)

    consulta_prevista.consulta = consulta
    consulta_prevista.status = ConsultaPrevista.Status.REALIZADA
    consulta_prevista.save(update_fields=["consulta", "status"])
    messages.success(
        request,
        f"Consulta {consulta_prevista.numero} vinculada à consulta de {consulta.data_hora:%d/%m/%Y} — o alerta some.",
    )
    return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=consultas")


@login_required
def fase_detalhe(request, pk):
    """
    Plano e avaliação de uma fase da modulação. Definir o plano ou registrar
    a avaliação pela primeira vez é livre pra qualquer profissional logado;
    alterar um plano ou uma avaliação já salvos exige administrador — mesma
    regra do Atendimento e da Anamnese, porque isso já é histórico clínico.
    """
    org = organizacao_do_usuario(request)
    fase = get_object_or_404(
        FaseModulacao.objects.select_related("modulacao__acompanhamento__paciente"),
        pk=pk, modulacao__acompanhamento__organizacao=org,
    )
    paciente = fase.modulacao.acompanhamento.paciente
    pode_editar_plano = fase.status == FaseModulacao.Status.PENDENTE or usuario_e_administrador(request)
    pode_editar_avaliacao = (
        fase.status != FaseModulacao.Status.CONCLUIDA or usuario_e_administrador(request)
    )

    fase_anterior = None
    if fase.numero > 1:
        fase_anterior = fase.modulacao.fases.filter(numero=fase.numero - 1).first()

    if request.method == "POST":
        qual_form = request.POST.get("form")
        if qual_form == "plano":
            if not pode_editar_plano:
                messages.error(request, "Só um administrador da clínica pode editar o plano dessa fase.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_plano = PlanoFaseForm(request.POST, instance=fase)
            if form_plano.is_valid():
                fase.iniciar_fase(
                    plano=form_plano.cleaned_data["plano"],
                    data_inicio=form_plano.cleaned_data.get("data_inicio"),
                )
                messages.success(request, f"Plano da fase {fase.numero} salvo.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_avaliacao = AvaliacaoFaseForm(instance=fase)
        elif qual_form == "avaliacao":
            if fase.status == FaseModulacao.Status.PENDENTE:
                messages.error(request, "Defina o plano dessa fase antes de registrar a avaliação.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            if not pode_editar_avaliacao:
                messages.error(request, "Só um administrador da clínica pode editar a avaliação dessa fase.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_avaliacao = AvaliacaoFaseForm(request.POST, instance=fase)
            if form_avaliacao.is_valid():
                fase.concluir_com_avaliacao(
                    resultado=form_avaliacao.cleaned_data["resultado"],
                    principais_melhoras=form_avaliacao.cleaned_data["principais_melhoras"],
                    o_que_trabalhar=form_avaliacao.cleaned_data["o_que_trabalhar"],
                )
                messages.success(request, f"Avaliação da fase {fase.numero} registrada.")
                return redirect("programas:fase_detalhe", pk=fase.pk)
            form_plano = PlanoFaseForm(instance=fase)
        else:
            messages.error(request, "Ação inválida.")
            return redirect("programas:fase_detalhe", pk=fase.pk)
    else:
        form_plano = PlanoFaseForm(instance=fase)
        form_avaliacao = AvaliacaoFaseForm(instance=fase)

    if not pode_editar_plano:
        for field in form_plano.fields.values():
            field.disabled = True
    if not pode_editar_avaliacao:
        for field in form_avaliacao.fields.values():
            field.disabled = True

    return render(request, "programas/fase_detalhe.html", {
        "paciente": paciente,
        "fase": fase,
        "fase_anterior": fase_anterior,
        "form_plano": form_plano,
        "form_avaliacao": form_avaliacao,
        "pode_editar_plano": pode_editar_plano,
        "pode_editar_avaliacao": pode_editar_avaliacao,
    })


@login_required
def feedback_criar(request, acompanhamento_pk):
    org = organizacao_do_usuario(request)
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=acompanhamento_pk, organizacao=org
    )
    if request.method == "POST":
        form = FeedbackForm(request.POST, acompanhamento=acompanhamento)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.acompanhamento = acompanhamento
            feedback.save()
            messages.success(request, "Feedback registrado.")
            return redirect(f"{reverse('pacientes:ficha', args=[acompanhamento.paciente.pk])}?aba=feedbacks")
    else:
        form = FeedbackForm(
            acompanhamento=acompanhamento,
            initial={"data_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M")},
        )
    return render(request, "programas/feedback_form.html", {
        "paciente": acompanhamento.paciente, "form": form, "feedback": None,
    })


@login_required
def feedback_editar(request, pk):
    """Registrar um feedback novo é livre; editar um já salvo exige administrador."""
    org = organizacao_do_usuario(request)
    feedback = get_object_or_404(
        Feedback.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    acompanhamento = feedback.acompanhamento
    pode_editar = usuario_e_administrador(request)

    if request.method == "POST":
        if not pode_editar:
            messages.error(request, "Só um administrador da clínica pode editar um feedback já salvo.")
            return redirect("programas:feedback_editar", pk=feedback.pk)
        form = FeedbackForm(request.POST, instance=feedback, acompanhamento=acompanhamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Feedback atualizado.")
            return redirect(f"{reverse('pacientes:ficha', args=[acompanhamento.paciente.pk])}?aba=feedbacks")
    else:
        form = FeedbackForm(instance=feedback, acompanhamento=acompanhamento)
        if not pode_editar:
            for field in form.fields.values():
                field.disabled = True
    return render(request, "programas/feedback_form.html", {
        "paciente": acompanhamento.paciente, "form": form, "feedback": feedback, "pode_editar": pode_editar,
    })


@login_required
def foto_criar(request, acompanhamento_pk):
    org = organizacao_do_usuario(request)
    acompanhamento = get_object_or_404(
        Acompanhamento.objects.select_related("paciente"), pk=acompanhamento_pk, organizacao=org
    )
    if request.method == "POST":
        form = FotoEvolucaoForm(request.POST, request.FILES)
        if form.is_valid():
            foto = form.save(commit=False)
            foto.acompanhamento = acompanhamento
            foto.enviada_por = request.user
            foto.save()
            messages.success(request, "Foto enviada.")
        else:
            messages.error(request, "Não deu pra enviar a foto — confira o formulário.")
    return redirect(f"{reverse('pacientes:ficha', args=[acompanhamento.paciente.pk])}?aba=fotos")


@login_required
@require_POST
def foto_excluir(request, pk):
    """Excluir uma foto de evolução já enviada exige administrador — subir uma nova é livre."""
    org = organizacao_do_usuario(request)
    foto = get_object_or_404(
        FotoEvolucao.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    paciente = foto.acompanhamento.paciente
    if not usuario_e_administrador(request):
        messages.error(request, "Só um administrador da clínica pode excluir uma foto de evolução.")
        return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=fotos")
    foto.delete()
    messages.success(request, "Foto excluída.")
    return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=fotos")


@login_required
def kit_montar(request, pk):
    """
    Escolhe os produtos que compõem esse kit e marca como enviado — dá baixa
    no estoque de cada produto escolhido e, quando o produto tem uma duração
    estimada, já agenda a próxima recompra da paciente pra esse produto.
    """
    org = organizacao_do_usuario(request)
    kit = get_object_or_404(
        KitPrevisto.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    paciente = kit.acompanhamento.paciente

    if kit.status == KitPrevisto.Status.ENVIADO:
        messages.error(request, "Esse kit já foi enviado.")
        return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=produtos")

    produtos_disponiveis = Produto.objects.filter(organizacao=org, ativo=True).order_by("nome")

    if request.method == "POST":
        produto_ids = request.POST.getlist("produto")
        quantidades = request.POST.getlist("quantidade")
        itens, erro = [], None
        for produto_id, quantidade_str in zip(produto_ids, quantidades):
            if not produto_id or not quantidade_str:
                continue
            produto = produtos_disponiveis.filter(pk=produto_id).first()
            try:
                quantidade = int(quantidade_str)
            except ValueError:
                quantidade = 0
            if not produto or quantidade <= 0:
                continue
            if quantidade > produto.estoque_atual:
                erro = (
                    f'Estoque insuficiente de "{produto.nome}" — '
                    f"disponível: {produto.estoque_atual}, pedido: {quantidade}."
                )
                break
            itens.append((produto, quantidade))

        if not erro and not itens:
            erro = "Escolha ao menos um produto pro kit."

        if erro:
            messages.error(request, erro)
        else:
            hoje = timezone.localdate()
            for produto, quantidade in itens:
                KitProdutoItem.objects.create(kit_previsto=kit, produto=produto, quantidade=quantidade)
                produto.estoque_atual -= quantidade
                produto.save(update_fields=["estoque_atual"])
                if produto.duracao_estimada_dias:
                    Recompra.objects.create(
                        organizacao=org, paciente=paciente, produto=produto,
                        data_prevista=hoje + datetime.timedelta(days=produto.duracao_estimada_dias),
                    )
            kit.status = KitPrevisto.Status.ENVIADO
            kit.data_envio = hoje
            kit.save(update_fields=["status", "data_envio"])
            messages.success(request, f"Kit {kit.numero} montado e marcado como enviado.")
            return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=produtos")

    return render(request, "programas/kit_form.html", {
        "paciente": paciente, "kit": kit, "produtos": produtos_disponiveis,
    })


@login_required
@require_POST
def kit_nao_se_aplica(request, pk):
    """
    Marca que esse kit não faz parte do que foi combinado com a paciente
    (ex.: consulta avulsa, sem produto incluso) — pra parar de aparecer
    o alerta "Kit N precisa ser enviado" sem precisar montar um kit que
    não existe.
    """
    org = organizacao_do_usuario(request)
    kit = get_object_or_404(
        KitPrevisto.objects.select_related("acompanhamento__paciente"),
        pk=pk, acompanhamento__organizacao=org,
    )
    paciente = kit.acompanhamento.paciente
    if kit.status == KitPrevisto.Status.PENDENTE:
        kit.status = KitPrevisto.Status.NAO_SE_APLICA
        kit.save(update_fields=["status"])
        messages.success(request, f"Kit {kit.numero} marcado como \"não se aplica\" — o alerta some.")
    return redirect(f"{reverse('pacientes:ficha', args=[paciente.pk])}?aba=produtos")
