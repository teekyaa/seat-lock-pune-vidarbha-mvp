"""WhatsApp Cloud API (Meta) authentication template for OTP delivery.

Sends an approved "authentication" category template with a copy-code button. The code is ours,
so verification stays local (only its hash is stored). Credentials never leave the API server.

A 200 response means Meta accepted the message, not that it was delivered: a number that is not
on WhatsApp still returns 200. The login screen therefore always offers "Send by SMS instead".
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .channels import SMSDeliveryError

WHATSAPP_TIMEOUT_SECONDS = 8


def whatsapp_messages_url():
    return (f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_VERSION}/"
            f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")


class WhatsAppOTPBackend:
    channel = "whatsapp"
    verifies_code = False

    def send_otp(self, phone, code):
        if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            raise SMSDeliveryError("WhatsApp credentials are incomplete.")
        payload = json.dumps({
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone.removeprefix("+"),
            "type": "template",
            "template": {
                "name": settings.WHATSAPP_OTP_TEMPLATE,
                "language": {"code": settings.WHATSAPP_OTP_LANGUAGE},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": code}]},
                    {"type": "button", "sub_type": "url", "index": "0",
                     "parameters": [{"type": "text", "text": code}]},
                ],
            },
        }).encode("utf-8")
        request = Request(
            whatsapp_messages_url(),
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "User-Agent": "SeatLock/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=WHATSAPP_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise SMSDeliveryError("WhatsApp did not accept the message.")
                result = json.load(response)
        except HTTPError as exc:
            # Never include the provider response, phone, code or token in errors.
            raise SMSDeliveryError(f"WhatsApp rejected the message (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise SMSDeliveryError("WhatsApp could not be reached or returned an invalid response.") from None

        messages = result.get("messages") if isinstance(result, dict) else None
        if not (isinstance(messages, list) and messages and isinstance(messages[0], dict)
                and isinstance(messages[0].get("id"), str)):
            raise SMSDeliveryError("WhatsApp did not accept the message.")
        return messages[0]["id"][:120]
