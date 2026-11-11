from django.urls import include, path

urlpatterns = [path("api/rsjc-backup/v1/", include("cloud_backup.urls"))]
