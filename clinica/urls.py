"""
URL configuration for clinica project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("financeiro/", include("financeiro.urls")),
    path("", include("core.urls")),
]

admin.site.site_header = "Sistema da Clínica"
admin.site.site_title = "Sistema da Clínica"
admin.site.index_title = "Administração"
