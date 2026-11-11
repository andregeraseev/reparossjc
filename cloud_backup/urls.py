from django.urls import path

from . import views

urlpatterns = [
    path("versions/", views.versions),
    path("versions/<int:version_id>/", views.download),
]
