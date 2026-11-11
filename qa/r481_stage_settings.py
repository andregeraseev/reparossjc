import json

from django.http import JsonResponse

from config.r48_settings import *


class SyntheticBackupOnly:
    """Accept the supplied QA job and its payment in the disposable environment."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST" or request.path != "/api/rsjc-backup/v1/versions/":
            return self.get_response(request)

        from cloud_backup.views import account_for

        if not request.is_secure() or account_for(request) is None:
            return self.get_response(request)
        length = request.META.get("CONTENT_LENGTH", "")
        if not length.isdecimal() or len(length) > 7 or not 0 < int(length) <= 256 * 1024:
            return self.reject()
        try:
            data = json.loads(request.body)
            job, = data["jobs"]
            payment, = data["payments"]
            if (job.get("id") != "qa-cloud-job" or job.get("client") != "Cliente fictício"
                    or payment.get("id") != "qa-pay" or payment.get("jobId") != job["id"]
                    or any(data.get(key) != [] for key in ("clients", "history", "inventory", "inventoryMovements",
                                                            "generalExpenses", "worklog", "tasks"))):
                return self.reject()
        except (AttributeError, KeyError, ValueError, TypeError, RecursionError):
            return self.reject()
        return self.get_response(request)

    @staticmethod
    def reject():
        return JsonResponse({"error": "qa_fixture_required"}, status=422, headers={"Cache-Control": "no-store"})


MIDDLEWARE = [*MIDDLEWARE, "qa.r481_stage_settings.SyntheticBackupOnly"]
