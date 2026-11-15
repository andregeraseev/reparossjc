import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone as utc
from functools import wraps
from ipaddress import ip_address

from django import forms
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from .models import LoginWindow, StaffAccount, StaffSession

COOKIE = "__Secure-rsjc_qa_staff"
COOKIE_PATH = "/qa/"
SESSION_SECONDS = 8 * 60 * 60
WINDOW_SECONDS = 300
ATTEMPTS_PER_ADDRESS = 10


class StaffLoginForm(forms.Form):
    username = forms.CharField(label="Usuário da equipe", max_length=48,
                               widget=forms.TextInput(attrs={"autocomplete": "username"}))
    password = forms.CharField(label="Senha", max_length=256, strip=False,
                               widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


def cookie_hash(token):
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return hashlib.sha256(token.encode("ascii")).hexdigest()
    return ""


def login_limit(request):
    origin = request.META.get("REMOTE_ADDR", "")
    if settings.RSJC_QA_TRUST_CLIENT_IP_PROXY:
        origin = request.headers.get("X-Real-IP", origin)
    try:
        address = str(ip_address(origin))
    except ValueError:
        address = "unavailable"

    timestamp = int(timezone.now().timestamp())
    window = timestamp - timestamp % WINDOW_SECONDS
    key = salted_hmac("rsjc.qa.login", f"{address}|{window}", algorithm="sha256").hexdigest()
    LoginWindow.objects.get_or_create(key=key, defaults={"started": datetime.fromtimestamp(window, utc.utc)})
    allowed = LoginWindow.objects.filter(key=key, attempts__lt=ATTEMPTS_PER_ADDRESS).update(attempts=F("attempts") + 1)
    if not allowed:
        return HttpResponse("Limite de tentativas atingido. Tente novamente em alguns minutos.", status=429,
                            headers={"Retry-After": str(window + WINDOW_SECONDS - timestamp)})


def private_qa(view):
    @never_cache
    @wraps(view)
    def checked(request, *args, **kwargs):
        response = view(request, *args, **kwargs) if request.is_secure() else HttpResponseForbidden("Acesso somente por HTTPS.")
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["Referrer-Policy"] = "same-origin"
        return response
    return checked


def staff_view(view):
    @private_qa
    @wraps(view)
    def checked(request, *args, **kwargs):
        key = cookie_hash(request.COOKIES.get(COOKIE, ""))
        if not key or not StaffSession.objects.filter(
                pk=key, expires_at__gt=timezone.now(), staff__enabled=True).exists():
            return redirect("qa_login")
        return view(request, *args, **kwargs)
    return checked


@private_qa
@require_http_methods(["GET", "POST"])
@csrf_protect
def login(request):
    form = StaffLoginForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        limited = login_limit(request)
        if limited is not None:
            return limited
        if form.is_valid():
            password = form.cleaned_data["password"]
            staff = StaffAccount.objects.filter(username=form.cleaned_data["username"].lower(), enabled=True).first()
            if staff is None:
                make_password(password)
            elif check_password(password, staff.password_hash):
                old_key = cookie_hash(request.COOKIES.get(COOKIE, ""))
                if old_key:
                    StaffSession.objects.filter(pk=old_key).delete()
                token = secrets.token_urlsafe(32)
                StaffSession.objects.create(key_hash=cookie_hash(token), staff=staff,
                                            expires_at=timezone.now() + timedelta(seconds=SESSION_SECONDS))
                response = redirect("qa_dashboard")
                response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, path=COOKIE_PATH,
                                    secure=True, httponly=True, samesite="Strict")
                return response
            form.add_error(None, "Usuário ou senha inválidos.")
    return render(request, "qa_monitor/login.html", {"form": form})


@private_qa
@require_POST
@csrf_protect
def logout(request):
    key = cookie_hash(request.COOKIES.get(COOKIE, ""))
    if key:
        StaffSession.objects.filter(pk=key).delete()
    response = redirect("qa_login")
    response.delete_cookie(COOKIE, path=COOKIE_PATH, samesite="Strict")
    return response
