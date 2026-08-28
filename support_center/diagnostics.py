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


def diagnose_account(account, devices, latest_snapshots, recent_events):
    findings = []
    now = timezone.now()
    device_list = list(devices)
    if not device_list:
        findings.append({"severity": "error", "code": "NO_DEVICE", "title": "Nenhum aparelho registrado", "detail": "A conta ainda não concluiu o bootstrap de suporte.", "recommendation": "Abrir Ajustes → Suporte no aparelho e atualizar o código."})
    for device in device_list:
        if device.last_seen_at and device.last_seen_at < now - timedelta(days=7):
            findings.append({"severity": "warn", "code": "DEVICE_STALE", "title": "Aparelho sem contato recente", "detail": f"{device.model or device.installation_id} não envia diagnóstico há mais de 7 dias.", "recommendation": "Confirmar internet e abrir o aplicativo antes do atendimento de suporte."})
        snap = latest_snapshots.get(str(device.id)) or {}
        backup = snap.get("backup") or {}
        backup_at = _parse_iso(backup.get("lastBackupAt"))
        if not backup_at:
            findings.append({"severity": "warn", "code": "NO_BACKUP", "title": "Backup recente não confirmado", "detail": device.model or device.installation_id, "recommendation": "Antes de qualquer correção de dados, gerar um backup pelo próprio app."})
        elif backup_at < now - timedelta(days=2):
            findings.append({"severity": "warn", "code": "BACKUP_OLD", "title": "Backup com mais de 48 horas", "detail": f"Último backup: {timezone.localtime(backup_at):%d/%m %H:%M}", "recommendation": "Gerar um backup antes de manutenção que altere dados."})
        sync = snap.get("sync") or {}
        if sync.get("corporateLastError"):
            findings.append({"severity": "error", "code": "CORPORATE_SYNC_ERROR", "title": "Erro na API corporativa", "detail": str(sync.get("corporateLastError"))[:180], "recommendation": "Verificar a linha do tempo e o status HTTP antes de alterar dados locais."})
        pending = int(sync.get("pendingCount") or 0)
        if pending > 0:
            findings.append({"severity": "warn", "code": "SYNC_PENDING", "title": f"{pending} alteração(ões) pendente(s)", "detail": "A fila local ainda possui itens não concluídos.", "recommendation": "Não limpar dados. Primeiro confirmar a conectividade e repetir a sincronização segura."})
        live = snap.get("liveUpdate") or {}
        if int((snap.get("device") or {}).get("androidSdk") or device.android_sdk or 0) >= 33 and live.get("notificationsAllowed") is False:
            findings.append({"severity": "warn", "code": "NOTIFICATIONS_BLOCKED", "title": "Notificações bloqueadas", "detail": "Live Update pode não aparecer no aparelho.", "recommendation": "Abrir as configurações de notificação pelo próprio app."})
        storage = snap.get("storage") or {}
        if float(storage.get("usagePercent") or 0) >= 90:
            findings.append({"severity": "warn", "code": "STORAGE_HIGH", "title": "Armazenamento do app próximo do limite", "detail": f"Uso estimado: {float(storage.get('usagePercent') or 0):.0f}%", "recommendation": "Gerar backup e revisar fotos/arquivos antes de limpar qualquer dado."})

    error_events = [e for e in recent_events if e.severity == "error"]
    if error_events:
        latest = error_events[0]
        findings.append({"severity": "error", "code": "RECENT_ERROR", "title": "Erro técnico recente", "detail": f"{latest.action}: {latest.detail.get('message') or latest.detail.get('code') or 'ver linha do tempo'}", "recommendation": "Abrir o evento na linha do tempo e correlacionar com a ação imediatamente anterior."})

    score = 100
    for finding in findings:
        score -= 22 if finding["severity"] == "error" else 8
    return max(0, score), findings[:12]
