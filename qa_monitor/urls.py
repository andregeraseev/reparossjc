from django.urls import path

from . import site_auth, views

urlpatterns = [
    path("qa/", views.dashboard, name="qa_dashboard"),
    path("qa/login/", site_auth.login, name="qa_login"),
    path("qa/logout/", site_auth.logout, name="qa_logout"),
    path("qa/panel.js", views.panel_script, name="qa_panel_script"),
    path("qa/sessions/<uuid:session_id>/", views.detail, name="qa_detail"),
    path("qa/bugs/", views.bugs, name="qa_bugs"),
    path("qa/bugs/<uuid:report_id>/", views.bug_detail, name="qa_bug_detail"),
    path("qa/bugs/<uuid:report_id>/screenshot/", views.bug_screenshot, name="qa_bug_screenshot"),
    path("api/rsjc-qa/v1/bugs/", views.submit_bug),
    path("api/rsjc-qa/v1/sessions/", views.submit),
    path("api/rsjc-qa/v1/identity/", views.tester_identity),
    path("api/rsjc-qa/v1/live/", views.submit_live),
]
