"""OTP delivery: try each configured sender in order until one accepts.

Order comes from settings.OTP_BACKENDS (WhatsApp first, then SMS). A user who asks for SMS skips
WhatsApp. Provider errors are logged without the phone number or code and never shown to users.
"""
import logging
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from apps.notifications.channels import SMSDeliveryError

log = logging.getLogger(__name__)


@dataclass
class Delivery:
    backend: str  # dotted path, stored on the challenge so verification uses the same provider
    channel: str  # "whatsapp" or "sms"
    reference: str  # provider message or verification id, may be empty
    verifies_code: bool


def configured_backends():
    return [(path, import_string(path)()) for path in settings.OTP_BACKENDS]


def sms_available():
    return any(backend.channel == "sms" for _, backend in configured_backends())


def deliver(phone, code, prefer=None):
    """Send the code. prefer="sms" skips WhatsApp. Raises SMSDeliveryError if every sender fails."""
    backends = configured_backends()
    if prefer == "sms":
        backends = [(path, b) for path, b in backends if b.channel == "sms"]
    if not backends:
        raise SMSDeliveryError("No OTP sender is configured for this channel.")
    for path, backend in backends:
        try:
            reference = backend.send_otp(phone, code) or ""
        except SMSDeliveryError as exc:
            log.warning("OTP sender %s failed: %s", path.rsplit(".", 1)[-1], exc)
            continue
        return Delivery(path, backend.channel, reference, bool(getattr(backend, "verifies_code", False)))
    raise SMSDeliveryError("Every OTP sender failed.")


def provider_check(backend_path, reference, code):
    """For senders that generate their own code. Returns 'ok', 'wrong' or 'expired'."""
    if backend_path not in settings.OTP_BACKENDS:
        return "expired"  # the sender was removed from config; ask for a new code
    return import_string(backend_path)().check(reference, code)
