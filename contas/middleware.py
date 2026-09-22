from django.contrib import messages
from django.shortcuts import redirect

from .models import Usuario

APPS_LIVRES_COMERCIAL = {"agenda", "leads"}
ROTAS_LIVRES_COMERCIAL = {("core", "home"), ("", "login"), ("", "logout")}


class RestringirAcessoComercialMiddleware:
    """
    Um usuário com papel "Comercial" (ex.: SDR/social selling) só acessa
    Agenda, CRM de leads e o painel "O que fazer hoje" — pedido pra dar
    acesso a uma pessoa da equipe sem expor ficha da paciente, prontuários,
    financeiro, indicadores, estoque, profissionais ou programas.

    Centralizado aqui como middleware (em vez de decorator em cada view)
    porque a restrição cobre apps inteiros de uma vez, sem precisar tocar
    em nenhum desses outros apps — nem eles precisam saber que esse papel
    existe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.papel != Usuario.Papel.COMERCIAL:
            return None

        match = request.resolver_match
        app_name = match.app_name if match else ""
        url_name = match.url_name if match else ""
        if app_name in APPS_LIVRES_COMERCIAL or (app_name, url_name) in ROTAS_LIVRES_COMERCIAL:
            return None

        messages.error(request, "Seu acesso é restrito à Agenda e ao CRM de leads.")
        return redirect("core:home")
