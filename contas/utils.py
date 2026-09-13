from django.core.exceptions import PermissionDenied


def organizacao_do_usuario(request):
    """
    Retorna a organização à qual as telas do sistema (painel do dia, kanban,
    agenda semanal, relatório financeiro) devem restringir os dados.

    Um administrador geral (superusuário sem organização) não tem uma
    organização "dona" das telas operacionais — essas telas são para o
    dia a dia de uma clínica específica. Por enquanto, pedimos para o
    administrador geral usar o `/admin/` para configurar organizações; o
    "alternar entre organizações" fica para uma próxima etapa.
    """

    organizacao = request.user.organizacao
    if organizacao is None:
        raise PermissionDenied(
            "Seu usuário não está vinculado a nenhuma organização. "
            "Peça para um administrador geral vincular seu usuário a uma "
            "organização em /admin/."
        )
    return organizacao
