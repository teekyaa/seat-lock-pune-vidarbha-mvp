"""TextBee request format and failure handling without sending real SMS."""
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from apps.notifications.channels import SMSDeliveryError
from apps.notifications.textbee import TEXTBEE_SEND_URL, TextBeeSMSBackend


def response(body, status=200):
    stream = io.BytesIO(json.dumps(body).encode("utf-8"))
    stream.status = status
    return stream


def test_textbee_sends_otp_with_server_side_credentials(settings, monkeypatch):
    settings.TEXTBEE_API_KEY = "test-only-api-key"
    settings.TEXTBEE_DEVICE_ID = "664a9b8cd0e1f2a3b4c5d6e7"
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response({"data": {"success": True, "smsBatchId": "batch-test", "recipientCount": 1}})

    monkeypatch.setattr("apps.notifications.textbee.urlopen", fake_urlopen)
    TextBeeSMSBackend().send_otp("+919876543210", "123456")

    request = captured["request"]
    assert request.full_url == TEXTBEE_SEND_URL
    assert request.get_method() == "POST"
    assert request.get_header("X-api-key") == "test-only-api-key"
    assert request.get_header("User-agent") == "SeatLock/0.1"
    assert captured["timeout"] > 0
    assert json.loads(request.data) == {
        "recipients": ["+919876543210"],
        "message": "Seat Lock code: 123456",
        "deviceId": "664a9b8cd0e1f2a3b4c5d6e7",
    }


@pytest.mark.parametrize("outcome", [
    HTTPError(TEXTBEE_SEND_URL, 401, "Unauthorized", {}, None),
    HTTPError(TEXTBEE_SEND_URL, 429, "Rate limited", {}, None),
    URLError("connection failed"),
    TimeoutError("timed out"),
])
def test_textbee_transport_errors_are_sanitized(settings, monkeypatch, outcome):
    settings.TEXTBEE_API_KEY = "test-only-api-key"
    settings.TEXTBEE_DEVICE_ID = "test-device"

    def fail(request, timeout):
        raise outcome

    monkeypatch.setattr("apps.notifications.textbee.urlopen", fail)
    with pytest.raises(SMSDeliveryError) as error:
        TextBeeSMSBackend().send_otp("+919876543210", "123456")
    assert "test-only-api-key" not in str(error.value)
    assert "123456" not in str(error.value)


@pytest.mark.parametrize("body", [
    {"data": {"success": False}},
    {"data": {"successCount": 0, "failureCount": 1}},
    {"unexpected": "response"},
])
def test_textbee_rejects_unaccepted_sends(settings, monkeypatch, body):
    settings.TEXTBEE_API_KEY = "test-only-api-key"
    settings.TEXTBEE_DEVICE_ID = "test-device"
    monkeypatch.setattr("apps.notifications.textbee.urlopen", lambda request, timeout: response(body))
    with pytest.raises(SMSDeliveryError):
        TextBeeSMSBackend().send_otp("+919876543210", "123456")


def test_textbee_requires_both_credentials(settings):
    settings.TEXTBEE_API_KEY = "test-only-api-key"
    settings.TEXTBEE_DEVICE_ID = ""
    with pytest.raises(SMSDeliveryError):
        TextBeeSMSBackend().send_otp("+919876543210", "123456")
