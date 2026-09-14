from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Consulta


@receiver(post_save, sender=Consulta)
def gerar_receita_prevista(sender, instance, created, **kwargs):
    """
    Ao agendar uma consulta de um tipo com valor definido, gera automaticamente
    um lançamento pendente no Financeiro (receita prevista) para esse valor.
    Não gera nada se o tipo de consulta não tem valor cadastrado, nem se esta
    consulta veio de um reagendamento (a cobrança já existe na consulta original).
    """
    if not created or instance.tipo_consulta.valor is None or instance.reagendada_de_id:
        return

    from financeiro.models import Pagamento

    Pagamento.objects.create(
        organizacao=instance.organizacao,
        paciente=instance.paciente,
        consulta=instance,
        valor=instance.tipo_consulta.valor,
        status=Pagamento.Status.PENDENTE,
        data_vencimento=instance.data_hora.date(),
    )
