"""Delivery channels. In-app is the row itself; email and Web Push are best effort on top.

SMS is used only for OTP, through a DLT-registered provider. The provider is not
chosen yet, so production must set SMS_BACKEND to a real implementation.
"""
import json
import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import send_mail
from django.utils.module_loading import import_string

log = logging.getLogger(__name__)


def valid_push_endpoint(endpoint):
    if not isinstance(endpoint, str) or len(endpoint) > 1000:
        return False
    try:
        url = urlsplit(endpoint)
        host = (url.hostname or "").lower()
        return (url.scheme == "https" and not url.username and not url.password and
                url.port in (None, 443) and
                (host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
                 or host.endswith(".push.apple.com")))
    except ValueError:
        return False


class SMSDeliveryError(Exception):
    """The SMS gateway did not accept an OTP for sending."""


class ConsoleSMSBackend:
    """Development only: prints the SMS instead of sending it."""

    def send_otp(self, phone, code):
        if not settings.DEBUG:
            raise SMSDeliveryError("Console SMS is disabled outside development.")
        log.warning("SMS to %s: Your Seat Lock code is %s. It expires in 5 minutes.", phone, code)


class UnconfiguredSMSBackend:
    def send_otp(self, phone, code):
        raise SMSDeliveryError("No SMS provider is configured.")


def sms_backend():
    return import_string(settings.SMS_BACKEND)()


def send_email(notification):
    user = notification.user
    if not user.email:
        return False
    link = f"{settings.WEB_BASE_URL}{notification.url}" if notification.url else settings.WEB_BASE_URL
    send_mail(
        subject=notification.title,
        message=f"{notification.body}\n\n{link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
    return True


def send_push(notification):
    if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY):
        return False
    from pywebpush import WebPushException, webpush

    sent = False
    payload = json.dumps({"title": notification.title, "body": notification.body, "url": notification.url})
    for sub in notification.user.push_subscriptions.all():
        if not valid_push_endpoint(sub.endpoint):
            raise ValueError("Unsupported push service endpoint")
        try:
            import requests

            class NoRedirectSession(requests.Session):
                def post(self, url, **kwargs):
                    kwargs["allow_redirects"] = False
                    return super().post(url, **kwargs)

            with NoRedirectSession() as session:
                webpush(
                    subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                    ttl=6 * 3600,
                    timeout=10,
                    requests_session=session,
                )
            sent = True
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                sub.delete()  # subscription is gone
            else:
                raise
    return sent
