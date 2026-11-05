import ipaddress
import logging
import uuid
from django.db import transaction

from apps.accounts.api import client_ip

from .models import AdminAuditEvent
from .logging import redact

log = logging.getLogger("seatlock.admin")


def record_event(request, action, *, admin=None, resource_type="", resource_id="", before=None, after=None, reason=""):
    try:
        address = str(ipaddress.ip_address(client_ip(request)))
    except ValueError:
        address = None
    event_id = getattr(request, "admin_request_id", None) or uuid.uuid4()
    event = AdminAuditEvent.objects.create(
        admin=admin,
        admin_role=admin.role if admin else "",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before=redact(before or {}),
        after=redact(after or {}),
        reason=redact(reason),
        request_id=event_id,
        ip_address=address,
        user_agent=redact(request.META.get("HTTP_USER_AGENT", "")[:300]),
    )
    transaction.on_commit(lambda: log.info("admin_event", extra={"event": action, "request_id": str(event_id),
        "context": {"admin_id": str(admin.pk) if admin else None, "resource_type": resource_type,
                    "resource_id": str(resource_id)}}))
    return event
