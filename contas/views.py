import datetime

from django.contrib.auth import views as auth_views
from django.utils import timezone

from .models import TentativaLoginFalha

LIMITE_TENTATIVAS = 5
JANELA_MINUTOS = 15


def ip_do_cliente(request):
    # Railway (e a maioria das hospedagens) fica atrás de um proxy, então o
    # IP real de quem acessa vem nesse cabeçalho, não em REMOTE_ADDR.
    forwardado = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwardado:
        return forwardado.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class LoginComLimiteDeTentativasView(auth_views.LoginView):
    """
    Bloqueia novas tentativas de login vindas do mesmo IP depois de muitas
    senhas erradas seguidas num intervalo curto — dificulta um ataque de
    força bruta tentando adivinhar a senha de alguém. O bloqueio é por IP,
    não por usuário, pra ninguém conseguir travar a conta de outra pessoa
    só errando a senha dela de propósito várias vezes.
    """

    def _bloqueado(self):
        limite = timezone.now() - datetime.timedelta(minutes=JANELA_MINUTOS)
        return TentativaLoginFalha.objects.filter(
            ip=ip_do_cliente(self.request), criado_em__gte=limite,
        ).count() >= LIMITE_TENTATIVAS

    def get(self, request, *args, **kwargs):
        if self._bloqueado():
            return self.render_to_response(
                self.get_context_data(bloqueado=True, minutos_bloqueio=JANELA_MINUTOS)
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self._bloqueado():
            return self.render_to_response(
                self.get_context_data(bloqueado=True, minutos_bloqueio=JANELA_MINUTOS)
            )
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        TentativaLoginFalha.objects.create(
            ip=ip_do_cliente(self.request),
            username=form.cleaned_data.get("username", "") or self.request.POST.get("username", ""),
        )
        # Descarta tentativas antigas (fora de qualquer janela de bloqueio
        # possível) pra tabela não crescer sem limite.
        limite_antigo = timezone.now() - datetime.timedelta(days=1)
        TentativaLoginFalha.objects.filter(criado_em__lt=limite_antigo).delete()
        return super().form_invalid(form)
