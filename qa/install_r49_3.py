"""Stage or switch the isolated PythonAnywhere QA overlay."""
import os
import re
import runpy
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
BASE = HOME / ".rsjc_qa_site"
ACTIVE = Path("/var/www/www_reparossjc_online_wsgi.py")
DB = BASE / "diagnostics.sqlite3"
RELEASE = BASE / "releases" / "r49-3"
MODULES = RELEASE / "modules"
BEFORE = RELEASE / "previous_wsgi.py"
CANDIDATE = RELEASE / "candidate_wsgi.py"
BACKUP = RELEASE / "qa-before-r49-3.sqlite3"
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
    shutil.copytree(SOURCE / "qa_monitor", MODULES / "qa_monitor", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--only-binary=:all:", "--target", str(MODULES),
                    "-r", str(SOURCE / "requirements-qa-feedback.txt")], check=True)
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
        raise RuntimeError("A migração exige o banco separado de QA.")
    call_command("check")
    if not BACKUP.exists():
        with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True, timeout=20) as source:
            with sqlite3.connect(BACKUP, timeout=20) as snapshot:
                source.backup(snapshot)
    call_command("migrate", "qa_monitor", database="rsjc_qa", interactive=False)
    client = Client(HTTP_HOST="www.reparossjc.online")
    if client.get("/", secure=True).status_code != 200:
        raise RuntimeError("A página pública falhou na verificação local.")
    if client.get("/qa/login/", secure=True).status_code != 200:
        raise RuntimeError("O login de QA falhou.")
    if client.get("/qa/bugs/", secure=True).status_code != 302:
        raise RuntimeError("Os relatos não estão protegidos pelo login.")
    response = client.post("/api/rsjc-qa/v1/bugs/", "{}", content_type="application/json", secure=True)
    if response.status_code != 401:
        raise RuntimeError("O endpoint de relatos não exigiu o token.")
    print("R493_PREPARADO: migração privada e rotas conferidas.")


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
    print("R493_WSGI_ATUALIZADO: recarregue o site no PythonAnywhere.")


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
