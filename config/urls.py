from django.contrib import admin
from django.urls import include, path
from meu_site.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include("corporate.urls")),
]
