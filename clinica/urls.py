"""
URL configuration for clinica project.
"""

import re

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("entrar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("leads/", include("leads.urls")),
    path("agenda/", include("agenda.urls")),
    path("pacientes/", include("pacientes.urls")),
    path("prontuarios/", include("prontuarios.urls")),
    path("financeiro/", include("financeiro.urls")),
    path("profissionais/", include("profissionais.urls")),
    path("programas/", include("programas.urls")),
    path("estoque/", include("estoque.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG or not settings.CLOUDINARY_STORAGE.get("CLOUD_NAME"):
    # Sem Cloudinary configurado, os arquivos enviados (fotos, documentos)
    # ficam no disco local do próprio servidor — sem essa rota, o upload
    # funciona mas o arquivo nunca fica acessível por URL nenhuma, em
    # produção ou não. Com Cloudinary configurado, essa rota nem é usada
    # (as URLs já apontam pra res.cloudinary.com).
    #
    # Não dá pra usar o helper `django.conf.urls.static.static()` pra isso:
    # ele mesmo se desliga sozinho sempre que DEBUG=False, então a rota
    # precisa ser montada à mão pra funcionar em produção também.
    urlpatterns += [
        re_path(
            r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")),
            serve_static,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

admin.site.site_header = "Sistema da Clínica"
admin.site.site_title = "Sistema da Clínica"
admin.site.index_title = "Administração"
