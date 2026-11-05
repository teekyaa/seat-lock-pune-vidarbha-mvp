"""WhatsApp and VerifyNow request formats, failure handling and the fallback chain. No real sends."""
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache

from apps.accounts import otp
from apps.notifications.channels import SMSDeliveryError
from apps.notifications.verifynow import VerifyNowSMSBackend
from apps.notifications.whatsapp import WhatsAppOTPBackend


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def response(body, status=200):
    stream = io.BytesIO(json.dumps(body).encode("utf-8"))
    stream.status = status
    return stream


def http_error(code, body=None):
    return HTTPError("https://example.invalid", code, "error", {}, io.BytesIO(json.dumps(body or {}).encode()))


@pytest.fixture
def whatsapp(settings):
    settings.WHATSAPP_ACCESS_TOKEN = "test-only-token"
    settings.WHATSAPP_PHONE_NUMBER_ID = "1234567890"
    settings.WHATSAPP_OTP_TEMPLATE = "seatlock_login_code"
    settings.WHATSAPP_OTP_LANGUAGE = "en"
    settings.WHATSAPP_GRAPH_VERSION = "v27.0"


def test_whatsapp_sends_authentication_template(whatsapp, monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"], captured["timeout"] = request, timeout
        return response({"messaging_product": "whatsapp", "messages": [{"id": "wamid.TEST"}]})

    monkeypatch.setattr("apps.notifications.whatsapp.urlopen", fake_urlopen)
    assert WhatsAppOTPBackend().send_otp("+919876543210", "123456") == "wamid.TEST"
    request = captured["request"]
    assert request.full_url == "https://graph.facebook.com/v27.0/1234567890/messages"
    assert request.get_header("Authorization") == "Bearer test-only-token"
    assert captured["timeout"] > 0
    body = json.loads(request.data)
    assert body["to"] == "919876543210" and body["type"] == "template"
    assert body["template"]["name"] == "seatlock_login_code"
    assert body["template"]["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "123456"}]},
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": "123456"}]},
    ]


@pytest.mark.parametrize("outcome", [http_error(400, {"error": {"message": "secret detail +919876543210"}}),
                                     URLError("down"), TimeoutError()])
def test_whatsapp_errors_are_sanitized(whatsapp, monkeypatch, outcome):
    def fake_urlopen(request, timeout):
        raise outcome

    monkeypatch.setattr("apps.notifications.whatsapp.urlopen", fake_urlopen)
    with pytest.raises(SMSDeliveryError) as error:
        WhatsAppOTPBackend().send_otp("+919876543210", "123456")
    assert "123456" not in str(error.value) and "9876543210" not in str(error.value)
    assert "secret detail" not in str(error.value) and "test-only-token" not in str(error.value)


def test_whatsapp_requires_a_message_id(whatsapp, monkeypatch):
    monkeypatch.setattr("apps.notifications.whatsapp.urlopen", lambda request, timeout: response({"messages": []}))
    with pytest.raises(SMSDeliveryError):
        WhatsAppOTPBackend().send_otp("+919876543210", "123456")


def test_whatsapp_requires_credentials(settings):
    settings.WHATSAPP_ACCESS_TOKEN = ""
    settings.WHATSAPP_PHONE_NUMBER_ID = ""
    with pytest.raises(SMSDeliveryError):
        WhatsAppOTPBackend().send_otp("+919876543210", "123456")


@pytest.fixture
def verifynow(settings):
    settings.VERIFYNOW_CUSTOMER_ID = "C-TEST"
    settings.VERIFYNOW_AUTH_KEY = "dGVzdC1vbmx5"


class FakeVerifyNow:
    """Routes requests by path; records each call."""

    def __init__(self, send=None, validate=None, unauthorised_once=False):
        self.calls = []
        self.send = send or {"responseCode": 200, "data": {"verificationId": 2949, "responseCode": "200"}}
        self.validate = validate
        self.unauthorised_once = unauthorised_once
        self.tokens = 0

    def __call__(self, request, timeout):
        url = urlsplit(request.full_url)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        self.calls.append((request.get_method(), url.path, params, request.get_header("Authtoken")))
        if url.path == "/auth/v1/authentication/token":
            self.tokens += 1
            return response({"status": 200, "token": f"token-{self.tokens}"})
        if self.unauthorised_once:
            self.unauthorised_once = False
            raise http_error(401)
        if url.path == "/verification/v3/send":
            return response(self.send)
        if url.path == "/verification/v3/validateOtp":
            status, body = self.validate
            if status != 200:
                raise http_error(status, body)
            return response(body)
        raise AssertionError(url.path)


def test_verifynow_send_gets_token_and_returns_verification_id(verifynow, monkeypatch):
    fake = FakeVerifyNow()
    monkeypatch.setattr("apps.notifications.verifynow.urlopen", fake)
    assert VerifyNowSMSBackend().send_otp("+919876543210", "ignored") == "2949"
    token_call, send_call = fake.calls
    assert token_call[2]["customerId"] == "C-TEST" and token_call[2]["key"] == "dGVzdC1vbmx5"
    method, path, params, token = send_call
    assert (method, path, token) == ("POST", "/verification/v3/send", "token-1")
    assert params["mobileNumber"] == "9876543210" and params["countryCode"] == "91"
    assert params["flowType"] == "SMS" and params["otpLength"] == "6"
    # The token is cached for the next send.
    VerifyNowSMSBackend().send_otp("+919876543210", "ignored")
    assert fake.tokens == 1


def test_verifynow_refreshes_an_expired_token(verifynow, monkeypatch):
    fake = FakeVerifyNow(unauthorised_once=True)
    monkeypatch.setattr("apps.notifications.verifynow.urlopen", fake)
    assert VerifyNowSMSBackend().send_otp("+919876543210", "ignored") == "2949"
    assert fake.tokens == 2


@pytest.mark.parametrize("validate, expected", [
    ((200, {"responseCode": 200, "data": {"verificationStatus": "VERIFICATION_COMPLETED", "responseCode": "200"}}), "ok"),
    ((400, {"responseCode": 702, "message": "WRONG_OTP_PROVIDED"}), "wrong"),
    ((400, {"responseCode": 705, "message": "VERIFICATION_EXPIRED"}), "expired"),
])
def test_verifynow_check_results(verifynow, monkeypatch, validate, expected):
    fake = FakeVerifyNow(validate=validate)
    monkeypatch.setattr("apps.notifications.verifynow.urlopen", fake)
    assert VerifyNowSMSBackend().check("2949", "123456") == expected
    assert fake.calls[-1][2]["verificationId"] == "2949" and fake.calls[-1][2]["code"] == "123456"


def test_verifynow_unknown_answers_and_outages_raise(verifynow, monkeypatch):
    monkeypatch.setattr("apps.notifications.verifynow.urlopen", FakeVerifyNow(validate=(500, {"responseCode": 500})))
    with pytest.raises(SMSDeliveryError):
        VerifyNowSMSBackend().check("2949", "123456")

    def down(request, timeout):
        raise URLError("down")

    monkeypatch.setattr("apps.notifications.verifynow.urlopen", down)
    with pytest.raises(SMSDeliveryError):
        VerifyNowSMSBackend().send_otp("+919876543210", "ignored")


def test_verifynow_rejects_a_send_without_verification_id(verifynow, monkeypatch):
    monkeypatch.setattr("apps.notifications.verifynow.urlopen",
                        FakeVerifyNow(send={"responseCode": 800, "data": {"responseCode": "800"}}))
    with pytest.raises(SMSDeliveryError):
        VerifyNowSMSBackend().send_otp("+919876543210", "ignored")


def sender(channel, fails=False, ref="", verifies=False):
    def send(phone, code):
        if fails:
            raise SMSDeliveryError("provider down")
        return ref

    return SimpleNamespace(channel=channel, verifies_code=verifies, send_otp=send)


def test_deliver_falls_back_from_whatsapp_to_sms(monkeypatch):
    monkeypatch.setattr(otp, "configured_backends", lambda: [
        ("x.WhatsApp", sender("whatsapp", fails=True)), ("x.SMS", sender("sms", ref="v-1", verifies=True)),
    ])
    delivery = otp.deliver("+919876543210", "123456")
    assert (delivery.backend, delivery.channel, delivery.reference, delivery.verifies_code) == (
        "x.SMS", "sms", "v-1", True)


def test_deliver_prefer_sms_skips_whatsapp(monkeypatch):
    used = []
    wa = sender("whatsapp")
    wa.send_otp = lambda phone, code: used.append("whatsapp")
    monkeypatch.setattr(otp, "configured_backends", lambda: [("x.WhatsApp", wa), ("x.SMS", sender("sms"))])
    assert otp.deliver("+919876543210", "123456", prefer="sms").channel == "sms"
    assert used == []


def test_deliver_raises_when_every_sender_fails(monkeypatch):
    monkeypatch.setattr(otp, "configured_backends", lambda: [("x.WhatsApp", sender("whatsapp", fails=True))])
    with pytest.raises(SMSDeliveryError):
        otp.deliver("+919876543210", "123456")
    with pytest.raises(SMSDeliveryError):
        otp.deliver("+919876543210", "123456", prefer="sms")  # no SMS sender configured


def test_provider_check_refuses_senders_not_in_config(settings):
    settings.OTP_BACKENDS = ["apps.notifications.whatsapp.WhatsAppOTPBackend"]
    assert otp.provider_check("os.system", "ref", "123456") == "expired"
