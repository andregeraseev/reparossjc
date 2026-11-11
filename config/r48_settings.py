"""Isolated QA deployment for the private Android backup API."""
import os
from pathlib import Path

SECRET_KEY = os.environ["RSJC_BACKUP_DJANGO_SECRET"]
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.environ["RSJC_BACKUP_HOSTS"].split(",") if host.strip()]
ROOT_URLCONF = "config.r48_urls"
INSTALLED_APPS = ["cloud_backup"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
RSJC_ENABLE_CLOUD_BACKUP = True

database = Path(os.environ["RSJC_BACKUP_DB"]).expanduser()
if not database.is_absolute():
    raise ValueError("RSJC_BACKUP_DB must be absolute")
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database,
                         "OPTIONS": {"timeout": 20}}}
SECURE_CONTENT_TYPE_NOSNIFF = True
if os.environ.get("RSJC_BACKUP_TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
