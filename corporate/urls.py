from django.urls import path
from . import logout_compat, portal_dispatch_v1830, views
from .auth import _with_operator_cors

app_name = "corporate"


def _health_with_cors(request):
    # O app Android usa uma página file:// dentro do WebView. Mesmo o GET simples
    # de health é cross-origin e precisa de Access-Control-Allow-Origin para que
    # fetch() consiga ler a resposta.
    return _with_operator_cors(views.health(request))


urlpatterns = [
    path("api/corporate/v1/health", _health_with_cors, name="health"),
    path("api/corporate/v1/operator/requests", views.operator_requests, name="operator_requests"),
    path("api/corporate/v1/operator/requests/<str:request_id>", views.operator_request_detail, name="operator_request_detail"),
    path("api/corporate/v1/operator/attachments/<str:attachment_id>", views.operator_attachment, name="operator_attachment"),
    path("api/corporate/v1/operator/availability", views.operator_availability, name="operator_availability"),
    path("api/corporate/v1/portal/requests", portal_dispatch_v1830.portal_requests_api, name="portal_requests_api"),
    path("corporativo/login/", views.CorporateLoginView.as_view(), name="login"),
    path("corporativo/logout/", logout_compat.corporate_logout, name="logout"),
    path("corporativo/", portal_dispatch_v1830.portal_home, name="portal"),
    path("corporativo/p/<slug:organization_slug>/<slug:channel_slug>/", portal_dispatch_v1830.portal_home, name="portal_channel"),
    path("corporativo/chamados/novo/", portal_dispatch_v1830.portal_create, name="portal_create"),
    path("corporativo/pessoas/salvar/", portal_dispatch_v1830.portal_person_save, name="portal_person_save"),
    path("corporativo/pessoas/<str:person_id>/alternar/", portal_dispatch_v1830.portal_person_toggle, name="portal_person_toggle"),
    path("corporativo/chamados/<str:request_id>/aprovar/", portal_dispatch_v1830.portal_approve, name="portal_approve"),
    path("corporativo/chamados/<str:request_id>/agendar/", portal_dispatch_v1830.portal_schedule, name="portal_schedule"),
    path("corporativo/anexos/<str:attachment_id>/", portal_dispatch_v1830.portal_attachment, name="portal_attachment"),
]
