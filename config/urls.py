from django.conf import settings
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

if settings.RSJC_QA_DB_PATH:
    urlpatterns.insert(0, path("", include("qa_monitor.urls")))
