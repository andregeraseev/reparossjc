from django.urls import path

from . import views

app_name = "support_center"

urlpatterns = [
    path("api/support/v1/health", views.api_health, name="api_health"),
    path("api/support/v1/bootstrap", views.api_bootstrap, name="api_bootstrap"),
    path("api/support/v1/consent", views.api_consent, name="api_consent"),
    path("api/support/v1/events", views.api_events, name="api_events"),
    path("api/support/v1/snapshot", views.api_snapshot, name="api_snapshot"),
    path("suporte/", views.dashboard, name="dashboard"),
    path("suporte/<str:support_code>/", views.account_detail, name="account_detail"),
    path("suporte/<str:support_code>/novo-chamado/", views.case_create, name="case_create"),
    path("suporte/<str:support_code>/chamado/<int:case_id>/status/", views.case_status, name="case_status"),
]
