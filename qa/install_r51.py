"""Stage or switch the isolated PythonAnywhere QA overlay."""
import os
import re
import runpy
import shutil
import sqlite3
import sys
from pathlib import Path

HOME = Path.home()
BASE = HOME / ".rsjc_qa_site"
ACTIVE = Path("/var/www/www_reparossjc_online_wsgi.py")
DB = BASE / "diagnostics.sqlite3"
RELEASE = BASE / "releases" / "r51"
MODULES = RELEASE / "modules"
BEFORE = RELEASE / "previous_wsgi.py"
CANDIDATE = RELEASE / "candidate_wsgi.py"
BACKUP = RELEASE / "qa-before-r51.sqlite3"
SOURCE = Path(__file__).resolve().parent.parent


def prepare():
    current = ACTIVE.read_bytes()
    text = current.decode()
    root = str(BASE / "releases")
    previous = set(re.findall(re.escape(root) + r"/[a-zA-Z0-9_-]+/modules", text))
    if len(previous) != 1 or not DB.is_file():
        raise RuntimeError("Instalação privada de QA não encontrada.")
    previous = previous.pop()
    if previous == str(MODULES) or not (Path(previous) / "qa_monitor").is_dir():
        raise RuntimeError("Origem de QA inesperada.")
    if not MODULES.is_dir():
        shutil.copytree(previous, MODULES, ignore=shutil.ignore_patterns("__pycache__"))
    for relative in ("views.py", "urls.py", "templates/qa_monitor/base.html",
                     "templates/qa_monitor/dashboard.html", "templates/qa_monitor/detail.html",
                     "templates/qa_monitor/panel.js"):
        source = SOURCE / "qa_monitor" / relative
        shutil.copy2(source, MODULES / "qa_monitor" / relative)
    candidate = text.replace(previous, str(MODULES))
    BEFORE.write_bytes(current)
    CANDIDATE.write_text(candidate)
    runpy.run_path(str(CANDIDATE))

    from django.conf import settings
    from django.core.management import call_command
    from django.test import Client

    if Path(settings.DATABASES["rsjc_qa"]["NAME"]).resolve() != DB.resolve():
        raise RuntimeError("O novo painel não apontou para o banco privado esperado.")
    if settings.DATABASES["default"]["NAME"] == settings.DATABASES["rsjc_qa"]["NAME"]:
        raise RuntimeError("O painel exige um banco separado para QA.")
    call_command("check")
    if not BACKUP.exists():
        with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True, timeout=20) as source:
            with sqlite3.connect(BACKUP, timeout=20) as snapshot:
                source.backup(snapshot)
    client = Client(HTTP_HOST="www.reparossjc.online")
    if client.get("/", secure=True).status_code != 200:
        raise RuntimeError("A página pública falhou na verificação local.")
    if client.get("/qa/login/", secure=True).status_code != 200:
        raise RuntimeError("O login de QA falhou.")
    if client.get("/qa/bugs/", secure=True).status_code != 302:
        raise RuntimeError("Os relatos não estão protegidos pelo login.")
    for route in ("bugs", "sessions", "identity", "live"):
        response = client.post(f"/api/rsjc-qa/v1/{route}/", "{}", content_type="application/json", secure=True)
        if response.status_code != 401:
            raise RuntimeError(f"O endpoint {route} não exigiu o token.")
    if client.get("/qa/panel.js", secure=True).status_code != 302:
        raise RuntimeError("O painel não está protegido pelo login.")
    print("R51_PREPARADO: banco privado, backup e rotas conferidos.")


def switch(original, replacement):
    before = original.read_bytes()
    updated = replacement.read_bytes()
    if ACTIVE.read_bytes() != before:
        raise RuntimeError("A configuração ativa mudou desde a preparação.")
    try:
        ACTIVE.write_bytes(updated)
        if ACTIVE.read_bytes() != updated:
            raise OSError("Não foi possível conferir o WSGI escrito.")
    except OSError:
        ACTIVE.write_bytes(before)
        raise
    print("R51_WSGI_ATUALIZADO: recarregue o site no PythonAnywhere.")


if __name__ == "__main__":
    os.umask(0o077)
    action = sys.argv[1]
    if action == "prepare":
        prepare()
    elif action == "apply":
        switch(BEFORE, CANDIDATE)
    elif action == "rollback":
        switch(CANDIDATE, BEFORE)
    else:
        raise SystemExit("Use prepare, apply ou rollback.")
