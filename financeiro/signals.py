from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Recebimento


@receiver(post_save, sender=Recebimento)
def recalcular_ao_salvar_recebimento(sender, instance, **kwargs):
    instance.pagamento.recalcular_status()


@receiver(post_delete, sender=Recebimento)
def recalcular_ao_excluir_recebimento(sender, instance, **kwargs):
    # o próprio recebimento já foi removido do banco nesse ponto, então
    # total_recebido já reflete a exclusão.
    instance.pagamento.recalcular_status()
