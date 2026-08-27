from django.shortcuts import render

def home(request):
    response = render(request, "home.html")

    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "

        "script-src 'self' 'unsafe-inline' "
        "https://www.googletagmanager.com "
        "https://www.google-analytics.com "
        "https://www.googleadservices.com "
        "https://googleads.g.doubleclick.net "
        "https://static.cloudflareinsights.com; "

        "connect-src 'self' "
        "https://www.google-analytics.com "
        "https://www.googletagmanager.com "
        "https://www.googleadservices.com "
        "https://googleads.g.doubleclick.net "
        "https://www.google.com "
        "https://static.cloudflareinsights.com; "

        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data: https:; "

        "frame-src "
        "https://www.googletagmanager.com "
        "https://googleads.g.doubleclick.net; "
    )

    response["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
    )

    return response

def seguranca(request):
    response = render(request, "seguranca.html")

    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "

        "script-src 'self' 'unsafe-inline' "
        "https://www.googletagmanager.com "
        "https://www.google-analytics.com "
        "https://www.googleadservices.com "
        "https://googleads.g.doubleclick.net "
        "https://static.cloudflareinsights.com; "

        "connect-src 'self' "
        "https://www.google-analytics.com "
        "https://www.googletagmanager.com "
        "https://www.googleadservices.com "
        "https://googleads.g.doubleclick.net "
        "https://www.google.com "
        "https://static.cloudflareinsights.com; "

        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data: https:; "

        "frame-src "
        "https://www.googletagmanager.com "
        "https://googleads.g.doubleclick.net; "
    )

    response["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), interest-cohort=()"
    )

    return response
