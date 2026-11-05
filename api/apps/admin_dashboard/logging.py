"""Structured admin events with defensive redaction of common sensitive fields."""
import json
import logging
import os
import re
from datetime import datetime, timezone

SENSITIVE_KEYS = ("password", "otp", "totp", "secret", "token", "api_key", "authorization", "upi", "phone", "email", "signature")
EMAIL_OR_UPI = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
INLINE_SECRET = re.compile(r"(?i)\b(?:otp|password|token|secret|api[_ -]?key|upi)\s*(?:is|:|=)\s*\S+")
EVENT = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


def redact(value):
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if any(secret in str(key).lower() for secret in SENSITIVE_KEYS) else redact(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return PHONE.sub("[REDACTED]", EMAIL_OR_UPI.sub("[REDACTED]", INLINE_SECRET.sub("[REDACTED]", value)))
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return "[REDACTED]"


class AdminJSONFormatter(logging.Formatter):
    def format(self, record):
        event = getattr(record, "event", "admin_event")
        if not isinstance(event, str) or not EVENT.fullmatch(event):
            event = "admin_event"
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "seatlock-api",
            "env": os.environ.get("APP_ENV", "development"),
            "request_id": getattr(record, "request_id", None),
            "event": event,
            "context": redact(getattr(record, "context", {})),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
