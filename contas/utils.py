import functools

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


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


def usuario_e_administrador(request):
    """
    Quem pode editar um registro do histórico clínico já criado (fase da
    modulação, avaliação, anamnese, foto de evolução, atendimento) — não é
    qualquer profissional logado, só quem administra a clínica. Reaproveita
    o `is_staff` que o Django já tem pronto em vez de criar um campo novo:
    marque essa caixinha no cadastro do usuário (em /admin/) para quem deve
    poder editar esses registros.

    Ações do dia a dia (agenda, leads, financeiro) não passam por aqui —
    essa checagem é só para edição de histórico clínico já registrado.
    """
    return request.user.is_authenticated and request.user.is_staff


def modulo_ativo_obrigatorio(campo_modulo, nome_exibicao):
    """
    Decorator de view: bloqueia o acesso a um módulo opcional (CRM de leads,
    Controle Financeiro, Programas/Acompanhamento) quando ele está desativado
    pra organização do usuário — evita que alguém chegue numa tela desligada
    digitando a URL direto. Use sempre depois de @login_required (nessa ordem:
    @login_required em cima, @modulo_ativo_obrigatorio embaixo).
    """
    def decorador(view_func):
        @functools.wraps(view_func)
        def view_decorada(request, *args, **kwargs):
            org = organizacao_do_usuario(request)
            if not getattr(org, campo_modulo):
                messages.error(request, f"O módulo {nome_exibicao} não está disponível pra sua organização.")
                return redirect("core:home")
            return view_func(request, *args, **kwargs)
        return view_decorada
    return decorador


def administrador_obrigatorio(view_func):
    """
    Decorator para views de edição de histórico clínico: bloqueia quem não
    é administrador da clínica (ver `usuario_e_administrador`), com uma
    mensagem clara em vez de um erro genérico. Combine com @login_required
    (nessa ordem: @login_required em cima, @administrador_obrigatorio embaixo)
    — este decorator presume que request.user já está autenticado.
    """
    @functools.wraps(view_func)
    def view_decorada(request, *args, **kwargs):
        if not usuario_e_administrador(request):
            messages.error(
                request,
                "Só um administrador da clínica pode editar esse registro já salvo.",
            )
            proximo = request.META.get("HTTP_REFERER")
            if proximo:
                return redirect(proximo)
            return redirect("core:home")
        return view_func(request, *args, **kwargs)
    return view_decorada
