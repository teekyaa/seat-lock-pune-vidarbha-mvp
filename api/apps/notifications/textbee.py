"""TextBee Android gateway for OTP delivery. Credentials never leave the API server."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .channels import SMSDeliveryError

TEXTBEE_SEND_URL = "https://api.textbee.dev/api/v1/gateway/send-sms"
TEXTBEE_TIMEOUT_SECONDS = 8


class TextBeeSMSBackend:
    def send_otp(self, phone, code):
        if not settings.TEXTBEE_API_KEY or not settings.TEXTBEE_DEVICE_ID:
            raise SMSDeliveryError("TextBee credentials are incomplete.")

        payload = json.dumps({
            "recipients": [phone],
            "message": f"Seat Lock code: {code}",
            "deviceId": settings.TEXTBEE_DEVICE_ID,
        }).encode("utf-8")
        request = Request(
            TEXTBEE_SEND_URL,
            data=payload,
            headers={
                "x-api-key": settings.TEXTBEE_API_KEY,
                "Content-Type": "application/json",
                "User-Agent": "SeatLock/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=TEXTBEE_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise SMSDeliveryError("TextBee did not accept the SMS.")
                result = json.load(response)
        except HTTPError as exc:
            # Do not include the provider response, request, phone, OTP, or API key in errors.
            raise SMSDeliveryError(f"TextBee rejected the SMS (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise SMSDeliveryError("TextBee could not be reached or returned an invalid response.") from None

        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict) or not (
            data.get("success") is True
            or (data.get("successCount") == 1 and data.get("failureCount") == 0)
        ):
            raise SMSDeliveryError("TextBee did not accept the SMS.")
