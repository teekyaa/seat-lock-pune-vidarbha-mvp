"""Access path for the legacy Django admin (/admin/).

The legacy admin has no TOTP, so production keeps it off unless DJANGO_LEGACY_ADMIN_ENABLED=1.
It is still the only place to manage route legs (docs/ROUTE_NETWORK_SPEC.md D3, D4) until the
new dashboard covers them, so when it is on it is reachable only from ADMIN_IP_ALLOWLIST.
Settings refuse to start production with the legacy admin on and no allowlist.
"""
import ipaddress

from django.conf import settings
from django.http import HttpResponseForbidden

from apps.accounts.api import client_ip

PREFIX = "/admin/"


class LegacyAdminAllowlistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(PREFIX) and settings.ADMIN_IP_ALLOWLIST and not _allowed(request):
            return HttpResponseForbidden("Admin access denied.")
        return self.get_response(request)


def _allowed(request):
    try:
        address = ipaddress.ip_address(client_ip(request))
    except ValueError:
        return False
    return any(address in network for network in settings.ADMIN_IP_ALLOWLIST)
