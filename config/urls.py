from django.contrib import admin
from django.urls import include, path
from meu_site.views import home, seguranca

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("seguranca", seguranca, name="seguranca"),
    path("", include("corporate.urls")),
    path("", include("support_center.urls")),
]
