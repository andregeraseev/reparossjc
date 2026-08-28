import hashlib
import re
import secrets

from django.db import transaction
from django.utils import timezone

from .models import SupportAccount, SupportDevice, SupportEvent, SupportSnapshot
from .services import (
    account_key_hash,
    clean_text,
    generate_support_code,
    parse_client_datetime,
    prune_device_data,
    safe_account_hash,
    safe_identifier,
    sanitize_detail,
    sanitize_snapshot,
    token_hash,
)

_SUPPORT_CODE_RE = re.compile(r"^RSJC-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")


def _offline_installation_id(account_hash, installation_id):
    raw = f"{account_hash}|{installation_id}".encode("utf-8")
    return "offline_" + hashlib.sha256(raw).hexdigest()[:32]


def _package_account_hash(payload, version):
    if version >= 3:
        return safe_account_hash(payload.get("supportAccountHash"))
    # Compatibility with Review1 packages that still carried the random account key.
    return account_key_hash(payload.get("supportAccountKey"))


def import_offline_package(payload):
    if not isinstance(payload, dict):
        raise ValueError("pacote inválido")
    if payload.get("format") != "ReparosSJC_Support_Diagnostic":
        raise ValueError("formato de diagnóstico não reconhecido")
    version = int(payload.get("version") or 0)
    if version not in {2, 3}:
        raise ValueError("versão de diagnóstico não suportada")

    account_hash = _package_account_hash(payload, version)
    installation_id = safe_identifier(payload.get("installationId"), prefix="installationId")
    snapshot = sanitize_snapshot(payload.get("snapshot") or {})
    workspace_id = clean_text((snapshot.get("workspace") or {}).get("workspaceId"), 100)
    app = snapshot.get("app") or {}
    device_info = snapshot.get("device") or {}
    requested_code = str(payload.get("supportCode") or "").strip().upper()[:20]

    with transaction.atomic():
        account = SupportAccount.objects.select_for_update().filter(account_key_hash=account_hash).first()
        if account is None:
            code = requested_code if _SUPPORT_CODE_RE.fullmatch(requested_code) and not SupportAccount.objects.filter(support_code=requested_code).exists() else generate_support_code()
            account = SupportAccount.objects.create(
                account_key_hash=account_hash,
                workspace_id=workspace_id,
                support_code=code,
                display_name="",
                last_seen_at=timezone.now(),
            )
        else:
            if workspace_id:
                account.workspace_id = workspace_id
            account.last_seen_at = timezone.now()
            account.save(update_fields=["workspace_id", "last_seen_at"])

        offline_id = _offline_installation_id(account_hash, installation_id)
        device, created = SupportDevice.objects.get_or_create(
            account=account,
            installation_id=offline_id,
            defaults={
                "token_hash": token_hash(secrets.token_urlsafe(48)),
                "platform": "offline",
                "manufacturer": clean_text(device_info.get("manufacturer"), 80),
                "model": clean_text(device_info.get("model") or "Pacote offline", 120),
                "android_release": clean_text(device_info.get("androidRelease"), 40),
                "android_sdk": max(0, int(device_info.get("androidSdk") or 0)),
                "app_version": clean_text(app.get("version"), 40),
                "app_version_code": max(0, int(app.get("versionCode") or 0)),
                "continuous_sharing": False,
                "privacy_version": clean_text((snapshot.get("support") or {}).get("privacyVersion") or "support-r1", 40),
                "active": True,
            },
        )
        if not created:
            device.manufacturer = clean_text(device_info.get("manufacturer"), 80)
            device.model = clean_text(device_info.get("model") or device.model or "Pacote offline", 120)
            device.android_release = clean_text(device_info.get("androidRelease"), 40)
            try:
                device.android_sdk = max(0, int(device_info.get("androidSdk") or 0))
                device.app_version_code = max(0, int(app.get("versionCode") or 0))
            except (TypeError, ValueError, OverflowError):
                pass
            device.app_version = clean_text(app.get("version"), 40)
            device.last_seen_at = timezone.now()
            device.save(update_fields=["manufacturer", "model", "android_release", "android_sdk", "app_version", "app_version_code", "last_seen_at"])

        SupportSnapshot.objects.create(account=account, device=device, data=snapshot)

        prepared = []
        for raw in (payload.get("events") or [])[:500]:
            if not isinstance(raw, dict):
                continue
            try:
                event_id = safe_identifier(raw.get("eventId"), prefix="eventId")
            except ValueError:
                continue
            action = clean_text(raw.get("action"), 100)
            entity = clean_text(raw.get("entity") or "system", 80)
            if not action:
                continue
            severity = str(raw.get("severity") or "info").lower()
            if severity not in {"info", "warn", "error"}:
                severity = "info"
            prepared.append(SupportEvent(
                account=account,
                device=device,
                event_id=f"offline:{event_id}"[:120],
                occurred_at=parse_client_datetime(raw.get("occurredAt")),
                action=action,
                entity=entity,
                severity=severity,
                detail=sanitize_detail(raw.get("detail") or {}),
                app_version=clean_text(app.get("version"), 40),
            ))
        SupportEvent.objects.bulk_create(prepared, ignore_conflicts=True, batch_size=100)
        prune_device_data(device)

    return account, device, len(prepared)
