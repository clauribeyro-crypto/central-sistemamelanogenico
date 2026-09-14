from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Consulta


@receiver(post_save, sender=Consulta)
def sincronizar_receita_prevista(sender, instance, created, **kwargs):
    """
    Mantém o lançamento do Financeiro (receita prevista) sincronizado com a
    consulta: cria ao agendar, atualiza valor/data/paciente se a consulta for
    editada, e cancela o lançamento se a consulta for cancelada ou ficar sem
    valor. Nunca mexe num lançamento que já foi marcado como Pago — dinheiro
    que já entrou não é desfeito automaticamente.
    """
    if instance.reagendada_de_id:
        # A cobrança já existe na consulta original — reagendamento não duplica.
        return

    from financeiro.models import Pagamento

    pagamento = Pagamento.objects.filter(consulta=instance).first()

    sem_cobranca = instance.status == Consulta.Status.CANCELADA or not instance.valor

    if sem_cobranca:
        if pagamento and pagamento.status == Pagamento.Status.PENDENTE:
            pagamento.status = Pagamento.Status.CANCELADO
            pagamento.save(update_fields=["status", "atualizado_em"])
        return

    if pagamento:
        if pagamento.status != Pagamento.Status.PENDENTE:
            return  # já foi pago (ou cancelado manualmente) — não sobrescreve
        campos_alterados = []
        if pagamento.valor != instance.valor:
            pagamento.valor = instance.valor
            campos_alterados.append("valor")
        if pagamento.paciente_id != instance.paciente_id:
            pagamento.paciente = instance.paciente
            campos_alterados.append("paciente")
        if pagamento.data_vencimento != instance.data_hora.date():
            pagamento.data_vencimento = instance.data_hora.date()
            campos_alterados.append("data_vencimento")
        if campos_alterados:
            pagamento.save(update_fields=[*campos_alterados, "atualizado_em"])
        return

    Pagamento.objects.create(
        organizacao=instance.organizacao,
        paciente=instance.paciente,
        consulta=instance,
        valor=instance.valor,
        status=Pagamento.Status.PENDENTE,
        data_vencimento=instance.data_hora.date(),
    )


@receiver(post_save, sender=Consulta)
def vincular_lead_por_correspondencia(sender, instance, created, **kwargs):
    """
    Ao agendar uma consulta sem vínculo explícito com um lead do CRM (ex.:
    paciente buscada/cadastrada direto no modal rápido da Agenda), procura um
    lead em cadência ativa com o mesmo telefone ou nome da paciente e move
    esse lead automaticamente para a aba "Agendados".
    """
    if not created or instance.lead_id:
        return  # já veio vinculado (ex.: agendado a partir do próprio lead)

    from leads.models import Lead

    lead = Lead.buscar_por_paciente(instance.organizacao, instance.paciente)
    if lead:
        lead.marcar_agendada(consulta=instance)
