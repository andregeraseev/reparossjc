from datetime import timedelta

from django.utils import timezone


def _parse_iso(value):
    if not value:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except (TypeError, ValueError):
        return None


def _score(findings):
    value = 100
    for finding in findings:
        value -= 22 if finding["severity"] == "error" else 8
    return max(0, value)


def diagnose_device(device, snapshot, recent_events):
    findings = []
    now = timezone.now()
    is_offline = device.platform == "offline"

    if not is_offline and device.last_seen_at and device.last_seen_at < now - timedelta(days=7):
        findings.append({
            "severity": "warn",
            "code": "DEVICE_STALE",
            "title": "Aparelho sem contato recente",
            "detail": f"{device.model or 'Aparelho'} não envia diagnóstico há mais de 7 dias.",
            "recommendation": "Confirmar internet e abrir o aplicativo antes do atendimento de suporte.",
        })

    backup = snapshot.get("backup") or {}
    backup_at = _parse_iso(backup.get("lastBackupAt"))
    if not backup_at:
        findings.append({
            "severity": "warn",
            "code": "NO_BACKUP",
            "title": "Backup recente não confirmado",
            "detail": device.model or "Fonte de diagnóstico",
            "recommendation": "Antes de qualquer correção de dados, gerar um backup pelo próprio app.",
        })
    elif backup_at < now - timedelta(days=2):
        findings.append({
            "severity": "warn",
            "code": "BACKUP_OLD",
            "title": "Backup com mais de 48 horas",
            "detail": f"Último backup: {timezone.localtime(backup_at):%d/%m %H:%M}",
            "recommendation": "Gerar um backup antes de manutenção que altere dados.",
        })

    sync = snapshot.get("sync") or {}
    corporate_error = str(sync.get("corporateLastErrorCode") or "").strip()
    if corporate_error:
        findings.append({
            "severity": "error",
            "code": "CORPORATE_SYNC_ERROR",
            "title": "Erro recente na API corporativa",
            "detail": corporate_error[:80],
            "recommendation": "Filtrar a linha do tempo por Corporate e confirmar HTTP/código antes de alterar dados locais.",
        })

    try:
        pending = int(sync.get("pendingCount") or 0)
    except (TypeError, ValueError, OverflowError):
        pending = 0
    if pending > 0:
        findings.append({
            "severity": "warn",
            "code": "SYNC_PENDING",
            "title": f"{pending} alteração(ões) pendente(s)",
            "detail": "A fila local ainda possui itens não concluídos.",
            "recommendation": "Não limpar dados. Primeiro confirmar a conectividade e repetir a sincronização segura.",
        })

    live = snapshot.get("liveUpdate") or {}
    try:
        sdk = int((snapshot.get("device") or {}).get("androidSdk") or device.android_sdk or 0)
    except (TypeError, ValueError, OverflowError):
        sdk = 0
    if not is_offline and sdk >= 33 and live.get("notificationsAllowed") is False:
        findings.append({
            "severity": "warn",
            "code": "NOTIFICATIONS_BLOCKED",
            "title": "Notificações bloqueadas",
            "detail": "Live Update pode não aparecer no aparelho.",
            "recommendation": "Abrir as configurações de notificação pelo próprio app.",
        })

    storage = snapshot.get("storage") or {}
    low_storage = storage.get("lowStorage") is True or (snapshot.get("device") or {}).get("lowStorage") is True
    try:
        free_percent = float(storage.get("freePercent") or 0)
    except (TypeError, ValueError, OverflowError):
        free_percent = 0.0
    if low_storage or (0 < free_percent <= 8):
        detail = f"Espaço livre: {free_percent:.1f}%" if free_percent else "O Android sinalizou pouco espaço livre."
        findings.append({
            "severity": "warn",
            "code": "STORAGE_LOW",
            "title": "Pouco armazenamento livre",
            "detail": detail,
            "recommendation": "Gerar backup e revisar fotos/arquivos antes de limpar qualquer dado.",
        })

    error_events = [event for event in recent_events if event.severity == "error"]
    if error_events:
        latest = error_events[0]
        detail = latest.detail or {}
        marker = detail.get("code") or detail.get("httpStatus") or detail.get("stackSignature") or "ver linha do tempo"
        findings.append({
            "severity": "error",
            "code": "RECENT_ERROR",
            "title": "Erro técnico recente",
            "detail": f"{latest.action}: {marker}",
            "recommendation": "Abrir o evento na linha do tempo e correlacionar com a ação imediatamente anterior.",
        })

    return _score(findings), findings[:10]


def diagnose_account(account, devices, latest_snapshots, recent_events):
    device_list = list(devices)
    if not device_list:
        findings = [{
            "severity": "error",
            "code": "NO_DEVICE",
            "title": "Nenhum aparelho registrado",
            "detail": "A conta ainda não concluiu o cadastro de suporte.",
            "recommendation": "Abrir Ajustes → Suporte no aparelho e atualizar o código.",
        }]
        return _score(findings), findings, None

    online_devices = [device for device in device_list if device.platform != "offline"]
    primary = (online_devices or device_list)[0]
    primary_events = [event for event in recent_events if event.device_id == primary.id]
    score, findings = diagnose_device(primary, latest_snapshots.get(str(primary.id)) or {}, primary_events)
    return score, findings, primary
