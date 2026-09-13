from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from agenda.models import Consulta
from contas.utils import organizacao_do_usuario
from pacientes.models import Paciente

from .forms import (
    AgendarConsultaForm, EnviarWhatsAppForm, PausarCadenciaForm,
    PerderLeadForm, RegistrarLigacaoForm, ResultadoContatoForm,
)
from .models import HistoricoLead, Lead, MensagemModelo

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

    return render(request, "leads/kanban.html", {"colunas": colunas, "contadores": contadores})


@login_required
def detalhe(request, pk):
    leads_qs, org = _leads_do_usuario(request)
    lead = get_object_or_404(leads_qs, pk=pk)
    historico = lead.historico.all()[:50]

    contexto = {
        "lead": lead,
        "historico": historico,
        "pausa_ativa": lead.pausa_ativa,
        "pode_agir": lead.status not in (Lead.Status.AGENDADA, Lead.Status.PERDIDA),
        "form_ligacao": RegistrarLigacaoForm(),
        "form_resultado": ResultadoContatoForm(),
        "mostrar_ligacao": (
            lead.etapa == Lead.Etapa.CONTATO_1
            and lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO)
            and lead.tentativas_etapa_atual < 2
        ),
        "numero_ligacao": lead.tentativas_etapa_atual + 1,
        "mostrar_whatsapp": (
            lead.status in (Lead.Status.PENDENTE, Lead.Status.EM_ANDAMENTO)
            and lead.etapa != Lead.Etapa.NOVO
            and not (lead.etapa == Lead.Etapa.CONTATO_1 and lead.tentativas_etapa_atual < 2)
        ),
    }
    return render(request, "leads/detalhe.html", contexto)


@login_required
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
