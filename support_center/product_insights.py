from collections import Counter
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import SupportEvent


def _num(detail, key):
    try:
        return max(0, int((detail or {}).get(key) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _pct(part, total):
    return round((100.0 * part / total), 1) if total else 0.0


def _avg(values):
    rows = [float(v) for v in values if v is not None and float(v) >= 0]
    return round(sum(rows) / len(rows), 1) if rows else 0.0


def summarize_product_events(events):
    """Aggregate R6 metadata only. No client/content fields are consulted."""
    rows = []
    for event in events:
        detail = getattr(event, "detail", None) or {}
        operation = str(detail.get("operation") or "")
        if not operation.startswith("ux_"):
            continue
        rows.append((event, detail, operation))

    operations = Counter(op for _event, _detail, op in rows)
    management = [d for _e, d, op in rows if op == "ux_management_session"]
    quotes = [d for _e, d, op in rows if op == "ux_quote_session"]
    jobs = [d for _e, d, op in rows if op == "ux_job_flow_session"]

    management_actioned = sum(1 for d in management if d.get("outcome") == "actioned")
    management_first = [_num(d, "firstActionMs") for d in management if d.get("outcome") == "actioned" and _num(d, "firstActionMs") > 0]
    quote_shared = sum(1 for d in quotes if d.get("outcome") == "shared")
    zero_searches = operations.get("ux_quote_search_zero", 0)
    quick_jobs = sum(1 for d in jobs if d.get("usedQuick") is True)
    voice_jobs = sum(1 for d in jobs if d.get("usedVoice") is True)
    job_backtracks = [_num(d, "backtrackCount") for d in jobs]
    slow_renders = operations.get("ux_management_slow_render", 0) + operations.get("ux_inventory_slow_render", 0)
    voice_results = operations.get("ux_voice_result", 0)

    metrics = {
        "events": len(rows),
        "management_sessions": len(management),
        "management_action_rate": _pct(management_actioned, len(management)),
        "management_first_action_ms": _avg(management_first),
        "quote_sessions": len(quotes),
        "quote_share_rate": _pct(quote_shared, len(quotes)),
        "zero_searches": zero_searches,
        "job_sessions": len(jobs),
        "avg_backtracks": _avg(job_backtracks),
        "quick_register_rate": _pct(quick_jobs, len(jobs)),
        "voice_job_rate": _pct(voice_jobs, len(jobs)),
        "voice_results": voice_results,
        "slow_renders": slow_renders,
    }

    signals = []
    if len(management) >= 5 and metrics["management_action_rate"] < 60:
        signals.append({"level": "warn", "title": "Gestão ainda muito consultiva", "detail": f"Só {metrics['management_action_rate']}% das sessões terminaram com alguma ação."})
    if len(management_first) >= 3 and metrics["management_first_action_ms"] > 15000:
        signals.append({"level": "warn", "title": "Demora para decidir na Gestão", "detail": f"Tempo médio até a primeira ação: {metrics['management_first_action_ms']/1000:.1f}s."})
    if len(quotes) >= 5 and zero_searches / max(1, len(quotes)) >= 0.20:
        signals.append({"level": "warn", "title": "Busca do catálogo merece revisão", "detail": f"Foram {zero_searches} buscas sem resultado em {len(quotes)} sessões de orçamento."})
    if len(jobs) >= 5 and metrics["avg_backtracks"] > 1.5:
        signals.append({"level": "warn", "title": "Fluxo de atendimento tem retorno excessivo", "detail": f"Média de {metrics['avg_backtracks']} volta(s) de etapa por sessão."})
    if len(jobs) >= 5 and metrics["quick_register_rate"] < 30:
        signals.append({"level": "info", "title": "Registro rápido pouco adotado", "detail": f"Usado em {metrics['quick_register_rate']}% das sessões de atendimento."})
    if slow_renders >= 3:
        signals.append({"level": "warn", "title": "Renderização lenta recorrente", "detail": f"{slow_renders} renderização(ões) acima do limite registradas."})
    if not signals and rows:
        signals.append({"level": "ok", "title": "Sem atrito forte detectado", "detail": "Os sinais coletados ainda não ultrapassam os limiares definidos para revisão."})

    top = [{"operation": op, "count": count} for op, count in operations.most_common(12)]
    versions = Counter(str(getattr(e, "app_version", "") or "-") for e, _d, _op in rows)
    return {"metrics": metrics, "signals": signals, "top_operations": top, "versions": versions.most_common(8)}


@staff_member_required
@never_cache
def dashboard(request):
    period = str(request.GET.get("period") or "30d").lower()
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    period = f"{days}d"
    since = timezone.now() - timedelta(days=days)
    events = list(
        SupportEvent.objects.filter(action="changed", occurred_at__gte=since)
        .select_related("device")
        .only("detail", "app_version", "occurred_at")
        .order_by("-occurred_at")[:20000]
    )
    summary = summarize_product_events(events)
    return render(request, "support_center/product_insights.html", {
        "period": period,
        "days": days,
        "summary": summary,
        "generated_at": timezone.now(),
    })
