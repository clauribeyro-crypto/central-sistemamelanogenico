from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def vincular_organizacao_unica_automaticamente(sender, instance, created, **kwargs):
    """
    Quando um usuário novo é criado sem organização e existe exatamente uma
    organização cadastrada no sistema, vincula automaticamente a ela.

    Evita o passo manual pelo /admin/ para o caso comum (uma clínica só,
    ainda sem outras "mentoradas" no sistema). Assim que existir mais de uma
    organização, esse atalho deixa de se aplicar sozinho — cada usuário novo
    passa a precisar ser vinculado manualmente à organização certa.
    """
    if not created or instance.organizacao_id is not None:
        return

    Organizacao = sender.organizacao.field.related_model
    organizacoes = Organizacao.objects.all()[:2]
    if len(organizacoes) == 1:
        instance.organizacao = organizacoes[0]
        instance.save(update_fields=["organizacao"])
