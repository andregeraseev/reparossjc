from django.urls import path
from . import views

app_name = "corporate"

urlpatterns = [
    path("api/corporate/v1/health", views.health, name="health"),
    path("api/corporate/v1/operator/requests", views.operator_requests, name="operator_requests"),
    path("api/corporate/v1/operator/requests/<str:request_id>", views.operator_request_detail, name="operator_request_detail"),
    path("api/corporate/v1/operator/availability", views.operator_availability, name="operator_availability"),
    path("api/corporate/v1/portal/requests", views.portal_requests_api, name="portal_requests_api"),
    path("corporativo/login/", views.CorporateLoginView.as_view(), name="login"),
    path("corporativo/logout/", views.CorporateLogoutView.as_view(), name="logout"),
    path("corporativo/", views.portal_home, name="portal"),
    path("corporativo/chamados/novo/", views.portal_create, name="portal_create"),
    path("corporativo/chamados/<str:request_id>/aprovar/", views.portal_approve, name="portal_approve"),
    path("corporativo/chamados/<str:request_id>/agendar/", views.portal_schedule, name="portal_schedule"),
]
