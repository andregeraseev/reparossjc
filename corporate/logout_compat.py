from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def corporate_logout(request):
    """Compatibility logout for portal templates.

    POST performs the logout. Legacy GET links render an explicit confirmation
    page instead of silently keeping a stale authenticated session.
    """
    if request.method == "POST":
        logout(request)
        return redirect("corporate:login")
    return render(request, "corporate/logout_confirm.html")
