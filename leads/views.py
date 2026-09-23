import calendar
import datetime
import json
from decimal import Decimal
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.forms import modelformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from agenda.models import Consulta
from contas.utils import modulo_ativo_obrigatorio, organizacao_do_usuario
from financeiro.models import Pagamento
from financeiro.views import MESES
from pacientes.models import Paciente
from programas.models import Acompanhamento

from .forms import (
    AgendarConsultaForm, EditarLeadForm, EnviarWhatsAppForm, NovoLeadForm, OrigemForm,
    PausarCadenciaForm, PerderLeadForm, RegistrarLigacaoForm, RegistroMarketingDiarioForm,
    RegistroSocialSellingForm, ResultadoContatoForm,
)
from .models import (
    HistoricoLead, Lead, MensagemModelo, Origem, PausaLead, RegistroMarketingDiario,
    RegistroSocialSelling, WebhookImportacao,
)

MENSAGENS_PADRAO = {
    MensagemModelo.Etapa.CONTATO_1: (
        "Oi, {nome}! Vi que você entrou em contato buscando informações sobre "
        "o nosso acompanhamento para melasma. Quando conseguir, me responde "
        "por aqui que eu te explico direitinho. ❤️"
    ),
    MensagemModelo.Etapa.CONTATO_2: (
        "Oi, {nome}! Passando novamente por aqui porque talvez ontem você não "
        "tenha conseguido me responder. Vi que você entrou em contato buscando "
        "informações sobre o nosso acompanhamento para melasma e queria "
        "entender um pouquinho melhor o seu caso. Quando conseguir, me "
        "responde por aqui. ❤️"
    ),
    MensagemModelo.Etapa.CONTATO_3: (
        "Oi, {nome}! Separei um caso parecido com o seu para você ver os "
        "resultados do nosso acompanhamento. Dá uma olhada e me conta o que "
        "achou! ❤️"
    ),
    MensagemModelo.Etapa.CONTATO_4: (
        "Oi, {nome}! Como não tivemos retorno nas nossas últimas tentativas de "
        "contato, vou encerrar seu atendimento por aqui para não ficar te "
        "incomodando.\n\nSe em algum momento você quiser entender melhor o que "
        "pode estar acontecendo com o seu melasma e conhecer nosso "
        "acompanhamento, pode nos chamar novamente. Estaremos à disposição. ❤️"
    ),
}


def _leads_do_usuario(request):
    org = organizacao_do_usuario(request)
    return Lead.objects.filter(organizacao=org), org


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def kanban(request):
    leads_qs, org = _leads_do_usuario(request)
    filtro = request.GET.get("filtro")

    status_por_filtro = {
        "pausados": Lead.Status.PAUSADO,
        "agendados": Lead.Status.AGENDADA,
        "sem_resposta": Lead.Status.SEM_RESPOSTA,
        "perdidos": Lead.Status.PERDIDA,
    }
    if filtro in status_por_filtro:
        leads = leads_qs.filter(status=status_por_filtro[filtro]).select_related(
            "origem", "responsavel"
        )
        return render(
            request, "leads/lista_filtrada.html",
            {"leads": leads, "filtro": filtro, "titulo": dict(
                [("pausados", "Pausados"), ("agendados", "Agendados"),
                 ("sem_resposta", "Sem resposta"), ("perdidos", "Perdidos")]
            )[filtro]},
        )

    ativos = leads_qs.filter(
        status__in=[Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO]
    ).select_related("origem", "responsavel")

    etapas_kanban = [e for e in Lead.Etapa.choices if e[0] != Lead.Etapa.CONCLUIDA]
    colunas = [(codigo, rotulo, []) for codigo, rotulo in etapas_kanban]
    colunas_por_codigo = {codigo: lista for codigo, _, lista in colunas}
    for lead in ativos:
        colunas_por_codigo[lead.etapa].append(lead)

    contadores = {
        chave: leads_qs.filter(status=status).count()
        for chave, status in status_por_filtro.items()
    }

    origens = Origem.objects.filter(organizacao=org, ativo=True)

    # Dataset pra busca cruzando abas: todo lead da organização, com a aba
    # e a etapa já resolvidas em texto — a busca em si roda no navegador.
    aba_por_status = {
        Lead.Status.PENDENTE: "Cadência ativa",
        Lead.Status.EM_ANDAMENTO: "Cadência ativa",
        Lead.Status.PAUSADO: "Pausados",
        Lead.Status.AGENDADA: "Agendados",
        Lead.Status.SEM_RESPOSTA: "Sem resposta",
        Lead.Status.PERDIDA: "Perdidos",
    }
    etapa_por_codigo = dict(Lead.Etapa.choices)
    leads_busca = [
        {
            "id": lead.pk,
            "nome": lead.nome,
            "telefone": f"{lead.whatsapp} {lead.telefone}".strip(),
            "status": lead.status,
            "aba": aba_por_status.get(lead.status, ""),
            "etapa": etapa_por_codigo.get(lead.etapa, ""),
        }
        for lead in leads_qs.only("id", "nome", "whatsapp", "telefone", "status", "etapa")
    ]

    return render(
        request, "leads/kanban.html",
        {"colunas": colunas, "contadores": contadores, "origens": origens, "leads_busca": leads_busca},
    )


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def origem_criar(request):
    """Cadastro de origem de lead (Indicação, Instagram...), livre pra qualquer usuária da organização."""
    org = organizacao_do_usuario(request)
    if request.method == "POST":
        form = OrigemForm(request.POST, organizacao=org)
        if form.is_valid():
            origem = form.save(commit=False)
            origem.organizacao = org
            origem.save()
            messages.success(request, "Origem cadastrada.")
            return redirect("leads:kanban")
    else:
        form = OrigemForm(organizacao=org)
    return render(request, "leads/origem_form.html", {"form": form})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def criar_lead(request):
    """Cadastro rápido de lead direto no board (botão "+ Novo lead")."""
    org = organizacao_do_usuario(request)
    form = NovoLeadForm(request.POST, organizacao=org)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)

    lead = form.save(commit=False)
    lead.organizacao = org
    lead.status = Lead.Status.PENDENTE
    lead.etapa = Lead.Etapa.NOVO
    lead.save()
    lead.registrar_historico(HistoricoLead.Tipo.ENTRADA, "Lead cadastrada manualmente pelo board", request.user)

    html = render_to_string("leads/_lead_card.html", {"lead": lead}, request=request)
    return JsonResponse({"ok": True, "html": html, "etapa": lead.etapa})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def registrar_social_selling(request):
    """Salva (ou atualiza) o registro de social selling de hoje da pessoa logada."""
    org = organizacao_do_usuario(request)
    registro, _ = RegistroSocialSelling.objects.get_or_create(
        organizacao=org, usuario=request.user, data=timezone.localdate(),
    )
    form = RegistroSocialSellingForm(request.POST, instance=registro)
    if form.is_valid():
        form.save()
        messages.success(request, "Números de hoje atualizados.")
    else:
        messages.error(request, "Não deu pra salvar — confira os números.")
    return redirect("core:home")


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def painel_marketing(request):
    """
    Visão diária de marketing e funil comercial pra gestora de tráfego.
    Investimento/impressões/cliques/pageview são lançados manualmente (o
    sistema não tem integração com Meta/Google Ads); leads, reuniões
    realizadas, vendas e valor são calculados a partir do que já existe no
    CRM de leads e no CRM de fechamento — não duplica lançamento nem corre
    o risco desses números baterem diferente do resto do sistema.
    """
    org = organizacao_do_usuario(request)
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

    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    data_inicio = datetime.date(ano, mes, 1)
    data_fim = min(datetime.date(ano, mes, ultimo_dia_mes), hoje)

    if data_fim >= data_inicio:
        dias_ja = set(RegistroMarketingDiario.objects.filter(
            organizacao=org, data__gte=data_inicio, data__lte=data_fim,
        ).values_list("data", flat=True))
        dia_atual = data_inicio
        novos = []
        while dia_atual <= data_fim:
            if dia_atual not in dias_ja:
                novos.append(RegistroMarketingDiario(organizacao=org, data=dia_atual))
            dia_atual += datetime.timedelta(days=1)
        if novos:
            RegistroMarketingDiario.objects.bulk_create(novos)

    queryset = RegistroMarketingDiario.objects.filter(
        organizacao=org, data__gte=data_inicio, data__lte=data_fim,
    ).order_by("data")
    FormSet = modelformset_factory(RegistroMarketingDiario, form=RegistroMarketingDiarioForm, extra=0)

    if request.method == "POST":
        formset = FormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Números de marketing salvos.")
            return redirect(f"{reverse('leads:painel_marketing')}?ano={ano}&mes={mes}")
        messages.error(request, "Não deu pra salvar — confira os números.")
    else:
        formset = FormSet(queryset=queryset)

    leads_por_dia = {
        row["entrou_em__date"]: row["total"]
        for row in Lead.objects.filter(
            organizacao=org, entrou_em__date__gte=data_inicio, entrou_em__date__lte=data_fim,
        ).values("entrou_em__date").annotate(total=Count("id"))
    }
    origens = list(Origem.objects.filter(organizacao=org, ativo=True).order_by("nome"))
    leads_por_dia_e_origem = {}
    for row in Lead.objects.filter(
        organizacao=org, entrou_em__date__gte=data_inicio, entrou_em__date__lte=data_fim,
    ).values("entrou_em__date", "origem_id").annotate(total=Count("id")):
        leads_por_dia_e_origem.setdefault(row["entrou_em__date"], {})[row["origem_id"]] = row["total"]
    reunioes_por_dia = {
        row["data_hora__date"]: row["total"]
        for row in Consulta.objects.filter(
            organizacao=org, status=Consulta.Status.REALIZADA,
            data_hora__date__gte=data_inicio, data_hora__date__lte=data_fim,
        ).values("data_hora__date").annotate(total=Count("id"))
    }
    fechamentos_do_periodo = Acompanhamento.objects.filter(
        organizacao=org, data_inicio__gte=data_inicio, data_inicio__lte=data_fim,
    ).prefetch_related("pagamentos")
    vendas_por_dia = {}
    valor_por_dia = {}
    for acompanhamento in fechamentos_do_periodo:
        # Mesma regra do relatório de fechamentos (financeiro.views.totais_fechamentos_mes):
        # o valor de verdade é o do pagamento vinculado, que pode ter sido corrigido
        # direto no Financeiro — valor_contratado só entra se não existir pagamento.
        pagamento = next(
            (p for p in acompanhamento.pagamentos.all() if p.status != Pagamento.Status.CANCELADO), None
        )
        valor_liquido = pagamento.valor if pagamento else (acompanhamento.valor_contratado - acompanhamento.desconto)
        vendas_por_dia[acompanhamento.data_inicio] = vendas_por_dia.get(acompanhamento.data_inicio, 0) + 1
        valor_por_dia[acompanhamento.data_inicio] = (
            valor_por_dia.get(acompanhamento.data_inicio, Decimal("0.00")) + valor_liquido
        )

    linhas = []
    for form in formset:
        data_linha = form.instance.data
        origens_do_dia = leads_por_dia_e_origem.get(data_linha, {})
        linhas.append({
            "form": form,
            "data": data_linha,
            "leads": leads_por_dia.get(data_linha, 0),
            "leads_por_origem": [origens_do_dia.get(o.pk, 0) for o in origens],
            "reunioes": reunioes_por_dia.get(data_linha, 0),
            "vendas": vendas_por_dia.get(data_linha, 0),
            "valor": valor_por_dia.get(data_linha, Decimal("0.00")),
        })

    totais = {
        "investimento": sum((l["form"].instance.investimento for l in linhas), Decimal("0.00")),
        "impressoes": sum((l["form"].instance.impressoes for l in linhas), 0),
        "cliques": sum((l["form"].instance.cliques for l in linhas), 0),
        "pageviews": sum((l["form"].instance.pageviews for l in linhas), 0),
        "leads": sum((l["leads"] for l in linhas), 0),
        "leads_por_origem": [
            sum((l["leads_por_origem"][i] for l in linhas), 0) for i in range(len(origens))
        ],
        "reunioes": sum((l["reunioes"] for l in linhas), 0),
        "vendas": sum((l["vendas"] for l in linhas), 0),
        "valor": sum((l["valor"] for l in linhas), Decimal("0.00")),
    }

    contexto = {
        "formset": formset,
        "linhas": linhas,
        "totais": totais,
        "origens": origens,
        "ano": ano,
        "mes": mes,
        "mes_nome": dict(MESES)[mes],
        "meses": MESES,
        "anos": range(hoje.year - 3, hoje.year + 2),
    }
    return render(request, "leads/painel_marketing.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def mover_etapa(request, pk):
    """Arrastar e soltar o card entre colunas do board."""
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    nova_etapa = request.POST.get("etapa")
    if nova_etapa not in Lead.ETAPAS_KANBAN:
        return JsonResponse({"ok": False, "erro": "Etapa inválida."}, status=400)
    lead.mover_para_etapa(nova_etapa, responsavel=request.user)
    return JsonResponse({"ok": True, "etapa": lead.etapa})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def marcar_respondido_rapido(request, pk):
    """Botão rápido do card: avança a cadência sem abrir a tela de detalhe."""
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    lead.marcar_respondido(responsavel=request.user)
    html = render_to_string("leads/_lead_card.html", {"lead": lead}, request=request)
    return JsonResponse({"ok": True, "etapa": lead.etapa, "html": html})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def mover_para_agendados(request, pk):
    """
    Fallback manual: arrastar o card do board direto pra aba "Agendados",
    para quando o vínculo automático (por telefone/nome) não pegar sozinho.
    Tenta achar a consulta correspondente para exibir na aba; se não achar,
    move o lead mesmo assim.
    """
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    consulta = lead.encontrar_consulta_correspondente()
    lead.marcar_agendada(consulta=consulta, responsavel=request.user)
    return JsonResponse({"ok": True})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def editar_lead(request, pk):
    """Editar os dados de contato de um lead (ex.: completar o telefone depois de abordar no Instagram)."""
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = EditarLeadForm(request.POST, instance=lead, organizacao=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do lead atualizados.")
            return redirect("leads:detalhe", pk=lead.pk)
    else:
        form = EditarLeadForm(instance=lead, organizacao=org)
    return render(request, "leads/editar.html", {"lead": lead, "form": form})


def _rotular_dados_formulario(dados_formulario):
    """Transforma as chaves cruas do formulário (ex.: 'qual_sua_renda') em rótulos legíveis."""
    rotulos = []
    for chave, valor in dados_formulario.items():
        rotulo = chave.replace("_", " ").replace("-", " ").strip()
        if rotulo and rotulo[0].islower():
            rotulo = rotulo[0].upper() + rotulo[1:]
        rotulos.append((rotulo or chave, valor))
    return rotulos


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def detalhe(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    historico = lead.historico.all()[:50]

    contexto = {
        "lead": lead,
        "dados_formulario": _rotular_dados_formulario(lead.dados_formulario),
        "historico": historico,
        "pausa_ativa": lead.pausa_ativa,
        "pode_agir": lead.status not in (Lead.Status.AGENDADA, Lead.Status.PERDIDA),
        "form_ligacao": RegistrarLigacaoForm(),
        "form_resultado": ResultadoContatoForm(),
        "mostrar_ligacao": (
            bool(lead.whatsapp or lead.telefone)
            and lead.etapa == Lead.Etapa.CONTATO_1
            and lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO)
            and lead.tentativas_etapa_atual < 2
        ),
        "numero_ligacao": lead.tentativas_etapa_atual + 1,
        "mostrar_whatsapp": (
            bool(lead.whatsapp)
            and lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO)
            and lead.etapa != Lead.Etapa.NOVO
            and not (lead.etapa == Lead.Etapa.CONTATO_1 and lead.tentativas_etapa_atual < 2)
        ),
        "mostrar_resultado_contato": (
            lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO)
            and lead.etapa != Lead.Etapa.NOVO
            and not (lead.etapa == Lead.Etapa.CONTATO_1 and lead.tentativas_etapa_atual < 2)
        ),
        "falta_contato": not lead.whatsapp and lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO),
    }
    return render(request, "leads/detalhe.html", contexto)


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def registrar_ligacao(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = RegistrarLigacaoForm(request.POST)
        if form.is_valid():
            numero = lead.tentativas_etapa_atual + 1
            resultado = form.cleaned_data["resultado"]
            if resultado == "ATENDEU":
                lead.status = Lead.Status.EM_ANDAMENTO
                lead.ultimo_contato_em = timezone.now()
                lead.save(update_fields=["status", "ultimo_contato_em", "atualizado_em"])
                lead.registrar_historico(
                    HistoricoLead.Tipo.LIGACAO, f"{numero}ª ligação — atendeu", request.user
                )
                messages.success(request, "Ligação registrada. Decida o próximo passo com a paciente.")
            else:
                lead.tentativas_etapa_atual = numero
                lead.ultimo_contato_em = timezone.now()
                lead.save(update_fields=["tentativas_etapa_atual", "ultimo_contato_em", "atualizado_em"])
                lead.registrar_historico(
                    HistoricoLead.Tipo.LIGACAO, f"{numero}ª ligação — não atendeu", request.user
                )
                if numero >= 2:
                    messages.info(request, "Duas ligações sem sucesso. Hora de enviar o WhatsApp do 1º contato.")
                else:
                    messages.info(request, "Sem sucesso na 1ª ligação. Tente a 2ª ligação.")
    return redirect("leads:detalhe", pk=lead.pk)


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def enviar_whatsapp(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)

    etapa_mensagem = lead.etapa if lead.etapa != Lead.Etapa.NOVO else MensagemModelo.Etapa.CONTATO_1
    modelo = MensagemModelo.objects.filter(
        organizacao=org, etapa=etapa_mensagem, ativo=True
    ).first()
    texto_padrao = modelo.render(lead) if modelo else MENSAGENS_PADRAO.get(
        etapa_mensagem, "Oi, {nome}!"
    ).format(nome=(lead.nome or "").split(" ")[0] or lead.nome)

    if request.method == "POST":
        form = EnviarWhatsAppForm(request.POST)
        if form.is_valid():
            texto = form.cleaned_data["texto"]
            lead.ultimo_contato_em = timezone.now()
            lead.save(update_fields=["ultimo_contato_em", "atualizado_em"])
            lead.registrar_historico(
                HistoricoLead.Tipo.WHATSAPP,
                f"WhatsApp enviado ({lead.get_etapa_display()})",
                request.user,
            )
            numero = "".join(ch for ch in lead.whatsapp if ch.isdigit())
            link = f"https://wa.me/{numero}?text={quote(texto)}"
            return redirect(link)
    else:
        form = EnviarWhatsAppForm(initial={"texto": texto_padrao})

    return render(request, "leads/enviar_whatsapp.html", {"lead": lead, "form": form})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def resultado_contato(request, pk):
    """Após uma mensagem de WhatsApp (ou ligação atendida): respondeu ou não respondeu."""
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = ResultadoContatoForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["resultado"] == "RESPONDEU":
                lead.status = Lead.Status.EM_ANDAMENTO
                lead.save(update_fields=["status", "atualizado_em"])
                lead.registrar_historico(HistoricoLead.Tipo.RESPOSTA, "Lead respondeu", request.user)
                messages.success(request, "Marcado como 'em andamento'. Decida o próximo passo.")
            else:
                etapa_anterior = lead.get_etapa_display()
                lead.avancar_etapa()
                lead.proxima_acao_em = timezone.now() + timezone.timedelta(days=1)
                lead.proxima_acao = f"Fazer {lead.get_etapa_display()}"
                lead.save(update_fields=["proxima_acao_em", "proxima_acao"])
                lead.registrar_historico(
                    HistoricoLead.Tipo.STATUS,
                    f"Sem resposta em {etapa_anterior} — avançou para {lead.get_etapa_display()}",
                    request.user,
                )
                if lead.etapa == Lead.Etapa.CONCLUIDA:
                    messages.warning(request, "Cadência encerrada: lead marcado como 'sem resposta'.")
                else:
                    messages.info(request, f"Lead avançou para {lead.get_etapa_display()}.")
    return redirect("leads:detalhe", pk=lead.pk)


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def pausar(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = PausarCadenciaForm(request.POST)
        if form.is_valid():
            lead.pausas.create(
                motivo=form.cleaned_data["motivo"],
                data_retomada_prevista=form.cleaned_data["data_retomada_prevista"],
                observacao=form.cleaned_data["observacao"],
                responsavel=request.user,
            )
            lead.status = Lead.Status.PAUSADO
            lead.save(update_fields=["status", "atualizado_em"])
            lead.registrar_historico(
                HistoricoLead.Tipo.PAUSA,
                f"Cadência pausada até {form.cleaned_data['data_retomada_prevista']:%d/%m/%Y} — {form.cleaned_data['motivo']}",
                request.user,
            )
            messages.success(request, "Cadência pausada.")
            return redirect("leads:detalhe", pk=lead.pk)
    else:
        form = PausarCadenciaForm()
    return render(request, "leads/pausar.html", {"lead": lead, "form": form})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def retomar(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    pausa = lead.pausa_ativa
    if request.method == "POST" and pausa:
        pausa.retomado_em = timezone.now()
        pausa.save(update_fields=["retomado_em"])
        lead.status = Lead.Status.EM_ANDAMENTO
        lead.save(update_fields=["status", "atualizado_em"])
        lead.registrar_historico(HistoricoLead.Tipo.RETOMADA, "Cadência retomada", request.user)
        messages.success(request, "Cadência retomada.")
    return redirect("leads:detalhe", pk=lead.pk)


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def excluir(request, pk):
    """
    Exclui a lead definitivamente (cadastro feito por engano, duplicado,
    teste etc.) — diferente de "Marcar como perdida", que mantém o registro
    no histórico. Consultas já agendadas a partir dessa lead não são
    afetadas, só perdem o vínculo com ela.
    """
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    nome = lead.nome
    lead.delete()
    messages.success(request, f"Lead \"{nome}\" excluída.")
    return redirect("leads:kanban")


def _normalizar_telefone(valor):
    return "".join(ch for ch in (valor or "") if ch.isdigit())


def _normalizar_nome(valor):
    return " ".join((valor or "").split()).strip().lower()


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def duplicados(request):
    """
    Agrupa leads que parecem ser a mesma pessoa cadastrada mais de uma vez —
    primeiro por telefone (WhatsApp ou telefone, normalizado sem formatação),
    o sinal mais confiável; leads sem telefone em comum mas com o mesmo nome
    entram num segundo grupo, pra não se perder entre cadastros repetidos.
    """
    leads_qs, org = _leads_do_usuario(request)
    leads = list(leads_qs.select_related("origem").order_by("-entrou_em"))

    por_telefone = {}
    for lead in leads:
        chave = _normalizar_telefone(lead.whatsapp) or _normalizar_telefone(lead.telefone)
        if chave:
            por_telefone.setdefault(chave, []).append(lead)
    grupos_telefone = [grupo for grupo in por_telefone.values() if len(grupo) > 1]

    pks_ja_agrupados = {lead.pk for grupo in grupos_telefone for lead in grupo}
    por_nome = {}
    for lead in leads:
        if lead.pk in pks_ja_agrupados:
            continue
        chave = _normalizar_nome(lead.nome)
        if chave:
            por_nome.setdefault(chave, []).append(lead)
    grupos_nome = [grupo for grupo in por_nome.values() if len(grupo) > 1]

    return render(request, "leads/duplicados.html", {
        "grupos_telefone": grupos_telefone,
        "grupos_nome": grupos_nome,
    })


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
@require_POST
def mesclar_duplicados(request):
    """
    Mescla um grupo de leads duplicadas numa só: transfere histórico, pausas
    e consultas vinculadas das descartadas para a mantida, preenche na
    mantida os campos que ela não tinha e as outras tinham, e por fim apaga
    as duplicatas.
    """
    leads_qs, org = _leads_do_usuario(request)
    try:
        manter_pk = int(request.POST.get("manter"))
        grupo_pks = [int(pk) for pk in request.POST.getlist("grupo")]
    except (TypeError, ValueError):
        messages.error(request, "Não deu pra mesclar — dados inválidos.")
        return redirect("leads:duplicados")

    if manter_pk not in grupo_pks:
        messages.error(request, "Não deu pra mesclar — dados inválidos.")
        return redirect("leads:duplicados")

    manter = get_object_or_404(leads_qs, pk=manter_pk)
    descartar_pks = [pk for pk in grupo_pks if pk != manter_pk]
    descartados = list(leads_qs.filter(pk__in=descartar_pks))
    if not descartados:
        messages.info(request, "Nada pra mesclar.")
        return redirect("leads:duplicados")

    for descartar in descartados:
        HistoricoLead.objects.filter(lead=descartar).update(lead=manter)
        PausaLead.objects.filter(lead=descartar).update(lead=manter)
        Consulta.objects.filter(lead=descartar).update(lead=manter)
        for campo in ("whatsapp", "telefone", "instagram", "cidade", "estado"):
            if not getattr(manter, campo) and getattr(descartar, campo):
                setattr(manter, campo, getattr(descartar, campo))
        if descartar.observacoes:
            separador = "\n\n" if manter.observacoes else ""
            manter.observacoes = (
                f"{manter.observacoes}{separador}[De \"{descartar.nome}\", mesclado] {descartar.observacoes}"
            )
        if descartar.dados_formulario:
            manter.dados_formulario = {**descartar.dados_formulario, **manter.dados_formulario}
        if descartar.paciente_id and not manter.paciente_id:
            manter.paciente = descartar.paciente
        nome_descartado = descartar.nome
        descartar.delete()
        manter.registrar_historico(
            HistoricoLead.Tipo.NOTA,
            f"Mesclado com lead duplicada \"{nome_descartado}\" (dados combinados, duplicata excluída).",
            request.user,
        )

    manter.save()
    messages.success(
        request,
        f"Mesclado! \"{manter.nome}\" agora reúne os dados de {len(descartados)} lead(s) duplicada(s).",
    )
    return redirect("leads:duplicados")


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def perder(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = PerderLeadForm(request.POST, organizacao=org)
        if form.is_valid():
            lead.status = Lead.Status.PERDIDA
            lead.perdido_motivo = form.cleaned_data["motivo"]
            lead.perdido_detalhe = form.cleaned_data["detalhe"]
            lead.save(update_fields=["status", "perdido_motivo", "perdido_detalhe", "atualizado_em"])
            lead.registrar_historico(
                HistoricoLead.Tipo.PERDA, f"Lead perdida — {lead.perdido_motivo}", request.user
            )
            messages.warning(request, "Lead marcada como perdida.")
            return redirect("leads:detalhe", pk=lead.pk)
    else:
        form = PerderLeadForm(organizacao=org)
    return render(request, "leads/perder.html", {"lead": lead, "form": form})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def agendar(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    if request.method == "POST":
        form = AgendarConsultaForm(request.POST, organizacao=org)
        if form.is_valid():
            paciente = lead.paciente
            if paciente is None:
                paciente = Paciente.objects.create(
                    organizacao=org, nome=lead.nome, telefone=lead.whatsapp,
                )
                lead.paciente = paciente

            data_hora = timezone.make_aware(
                timezone.datetime.combine(form.cleaned_data["data"], form.cleaned_data["hora"])
            )
            consulta = Consulta.objects.create(
                organizacao=org,
                paciente=paciente,
                profissional=form.cleaned_data["profissional"],
                tipo_consulta=form.cleaned_data["tipo_consulta"],
                lead=lead,
                data_hora=data_hora,
                duracao_minutos=form.cleaned_data["duracao_minutos"],
                observacoes=form.cleaned_data["observacoes"],
            )
            lead.status = Lead.Status.AGENDADA
            lead.save(update_fields=["status", "paciente", "atualizado_em"])
            lead.registrar_historico(
                HistoricoLead.Tipo.AGENDAMENTO,
                f"Consulta agendada para {data_hora:%d/%m/%Y %H:%M} com {consulta.profissional}",
                request.user,
            )
            messages.success(request, "Consulta agendada! A cadência foi interrompida.")
            return redirect("leads:detalhe", pk=lead.pk)
    else:
        form = AgendarConsultaForm(organizacao=org)
    return render(request, "leads/agendar.html", {"lead": lead, "form": form})


@csrf_exempt
@require_POST
def webhook_importar_lead(request, token):
    """
    Recebe leads automaticamente de fora do sistema (ex.: um Google Apps
    Script vinculado à planilha do Respondi, disparado a cada nova resposta
    de formulário). O token na URL é a autenticação — sem sessão, sem CSRF.
    Aceita tanto JSON quanto form-urlencoded no corpo do POST.
    """
    webhook = WebhookImportacao.objects.filter(token=token, ativo=True).first()
    if not webhook:
        return JsonResponse({"ok": False, "erro": "Token inválido."}, status=404)

    if request.content_type == "application/json":
        try:
            dados = json.loads(request.body or "{}")
        except ValueError:
            return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)
    else:
        dados = request.POST

    CAMPOS_RECONHECIDOS = {
        "nome", "name", "telefone", "whatsapp", "phone", "origem",
        "data", "data_primeiro_contato", "timestamp",
    }
    dados_extras = {
        chave: valor for chave, valor in dados.items()
        if chave not in CAMPOS_RECONHECIDOS and str(valor).strip()
    }

    nome = dados.get("nome") or dados.get("name") or ""
    telefone = dados.get("telefone") or dados.get("whatsapp") or dados.get("phone") or ""

    origem = None
    nome_origem = (dados.get("origem") or "").strip()
    if nome_origem:
        origem = Origem.objects.filter(organizacao=webhook.organizacao, nome__iexact=nome_origem).first()

    data_primeiro_contato = None
    valor_data = dados.get("data") or dados.get("data_primeiro_contato") or dados.get("timestamp")
    if valor_data:
        data_primeiro_contato = parse_datetime(valor_data)
        if not data_primeiro_contato:
            # aceita também "dd/mm/aaaa hh:mm:ss", formato comum de planilha do Google
            try:
                data_primeiro_contato = timezone.datetime.strptime(valor_data, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                data_primeiro_contato = None
        if data_primeiro_contato and timezone.is_naive(data_primeiro_contato):
            data_primeiro_contato = timezone.make_aware(data_primeiro_contato)

    lead, criado, motivo = webhook.registrar_lead_importado(
        nome=nome, telefone=telefone, origem=origem, data_primeiro_contato=data_primeiro_contato,
        dados_extras=dados_extras,
    )
    if lead is None:
        return JsonResponse({"ok": False, "erro": motivo}, status=400)
    return JsonResponse({"ok": True, "criado": criado, "lead_id": lead.pk, "motivo": motivo})


@login_required
@modulo_ativo_obrigatorio("modulo_leads_ativo", "CRM de leads")
def configuracao_importacao(request):
    """Tela de configuração do webhook de importação automática de leads."""
    org = organizacao_do_usuario(request)
    webhook = WebhookImportacao.objects.filter(organizacao=org).first()

    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "criar" and not webhook:
            origem_padrao = Origem.objects.filter(organizacao=org, ativo=True).first()
            if not origem_padrao:
                messages.error(request, "Cadastre pelo menos uma origem de lead antes de criar o webhook.")
                return redirect("leads:configuracao_importacao")
            webhook = WebhookImportacao.objects.create(organizacao=org, origem_padrao=origem_padrao)
            messages.success(request, "Webhook de importação criado.")
        elif acao == "regenerar_token" and webhook:
            webhook.gerar_novo_token()
            messages.success(request, "Token regenerado — atualize a URL onde ela estiver configurada.")
        elif acao == "mudar_origem" and webhook:
            nova_origem = get_object_or_404(Origem, pk=request.POST.get("origem_padrao"), organizacao=org)
            webhook.origem_padrao = nova_origem
            webhook.save(update_fields=["origem_padrao"])
            messages.success(request, "Origem padrão atualizada.")
        elif acao == "alternar_ativo" and webhook:
            webhook.ativo = not webhook.ativo
            webhook.save(update_fields=["ativo"])
            messages.success(request, "Webhook ativado." if webhook.ativo else "Webhook desativado.")
        return redirect("leads:configuracao_importacao")

    url_webhook = None
    if webhook:
        url_webhook = request.build_absolute_uri(
            reverse("leads:webhook_importar_lead", kwargs={"token": webhook.token})
        )
    contexto = {
        "webhook": webhook,
        "url_webhook": url_webhook,
        "origens": Origem.objects.filter(organizacao=org, ativo=True),
    }
    return render(request, "leads/configuracao_importacao.html", contexto)
