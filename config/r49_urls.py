from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from qa_monitor import views

urlpatterns = [
    path("api/rsjc-qa/v1/sessions/", views.submit),
    path("qa/", views.dashboard, name="qa_dashboard"),
    path("qa/sessions/<uuid:session_id>/", views.detail, name="qa_detail"),
    path("qa/login/", LoginView.as_view(template_name="qa_monitor/login.html"), name="qa_login"),
    path("qa/logout/", LogoutView.as_view(), name="qa_logout"),
]
