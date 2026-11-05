"""The legacy Django admin is reachable only from ADMIN_IP_ALLOWLIST when one is set."""
import ipaddress

from django.http import HttpResponse
from django.test import RequestFactory

from apps.admin_dashboard.legacy_admin import LegacyAdminAllowlistMiddleware

middleware = LegacyAdminAllowlistMiddleware(lambda request: HttpResponse("ok"))


def get(path, ip):
    return middleware(RequestFactory().get(path, REMOTE_ADDR=ip))


def test_blocks_admin_outside_allowlist(settings):
    settings.ADMIN_IP_ALLOWLIST = [ipaddress.ip_network("10.0.0.0/24")]
    assert get("/admin/routes/leg/", "203.0.113.9").status_code == 403
    assert get("/admin/routes/leg/", "10.0.0.7").status_code == 200


def test_other_paths_untouched(settings):
    settings.ADMIN_IP_ALLOWLIST = [ipaddress.ip_network("10.0.0.0/24")]
    assert get("/api/v1/rides", "203.0.113.9").status_code == 200


def test_no_allowlist_means_no_restriction_in_development(settings):
    settings.ADMIN_IP_ALLOWLIST = []
    assert get("/admin/", "203.0.113.9").status_code == 200
