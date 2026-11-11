"""Django isolated for opt-in Android QA diagnostics."""
import os
from pathlib import Path

SECRET_KEY = os.environ["RSJC_QA_SECRET"]
DEBUG = False
ALLOWED_HOSTS = os.environ["RSJC_QA_HOSTS"].split()
ROOT_URLCONF = "config.r49_urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes",
                  "django.contrib.sessions", "qa_monitor"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware",
              "django.contrib.sessions.middleware.SessionMiddleware",
              "django.middleware.csrf.CsrfViewMiddleware",
              "django.contrib.auth.middleware.AuthenticationMiddleware",
              "django.middleware.clickjacking.XFrameOptionsMiddleware"]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]
database = Path(os.environ["RSJC_QA_DATABASE"]).expanduser()
if not database.is_absolute():
    raise ValueError("RSJC_QA_DATABASE must be absolute")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database,
                         "OPTIONS": {"timeout": 20}}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "America/Sao_Paulo"
LANGUAGE_CODE = "pt-br"
USE_TZ = True
LOGIN_URL = "/qa/login/"
LOGIN_REDIRECT_URL = "/qa/"
LOGOUT_REDIRECT_URL = LOGIN_URL
SESSION_COOKIE_NAME = "rsjc_r49_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_NAME = "rsjc_r49_csrf"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = True
if os.environ.get("RSJC_QA_TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
