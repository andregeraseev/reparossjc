from django.urls import path

from . import site_auth, views

urlpatterns = [
    path("qa/", views.dashboard, name="qa_dashboard"),
    path("qa/login/", site_auth.login, name="qa_login"),
    path("qa/logout/", site_auth.logout, name="qa_logout"),
    path("qa/sessions/<uuid:session_id>/", views.detail, name="qa_detail"),
    path("api/rsjc-qa/v1/sessions/", views.submit),
]
