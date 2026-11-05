"""Message Central VerifyNow: SMS OTP for India without our own DLT registration.

VerifyNow generates and checks the code itself, so the challenge stores only its verificationId
and verification calls the provider. Credentials and the short-lived auth token stay server-side.
API reference: https://www.messagecentral.com/product/verify-now/api-india (v3).
"""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .channels import SMSDeliveryError

VERIFYNOW_BASE_URL = "https://cpaas.messagecentral.com"
VERIFYNOW_TIMEOUT_SECONDS = 8
TOKEN_CACHE_KEY = "otp:verifynow:token"
TOKEN_CACHE_SECONDS = 30 * 60  # lifetime is undocumented, so refresh well before any likely expiry

# Provider response codes (from the v3 docs).
WRONG_CODES = {700, 702, 703}  # failed, wrong OTP, already verified
EXPIRED_CODES = {705}


class _Unauthorised(Exception):
    pass


def _parse(raw):
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _response_code(body):
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    for value in (data.get("responseCode"), body.get("responseCode")):
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


class VerifyNowSMSBackend:
    channel = "sms"
    verifies_code = True

    def _call(self, method, path, params, token=None):
        headers = {"accept": "application/json", "User-Agent": "SeatLock/0.1"}
        if token:
            headers["authToken"] = token
        request = Request(f"{VERIFYNOW_BASE_URL}{path}?{urlencode(params)}", headers=headers, method=method,
                          data=b"" if method == "POST" else None)
        try:
            with urlopen(request, timeout=VERIFYNOW_TIMEOUT_SECONDS) as response:
                return response.status, _parse(response.read())
        except HTTPError as exc:
            if exc.code == 401:
                raise _Unauthorised() from None
            # Error bodies carry the provider's responseCode; never surface the rest.
            try:
                return exc.code, _parse(exc.read())
            except OSError:
                return exc.code, {}
        except (URLError, TimeoutError, OSError):
            raise SMSDeliveryError("VerifyNow could not be reached.") from None

    def _token(self, refresh=False):
        if not refresh:
            token = cache.get(TOKEN_CACHE_KEY)
            if token:
                return token
        if not settings.VERIFYNOW_CUSTOMER_ID or not settings.VERIFYNOW_AUTH_KEY:
            raise SMSDeliveryError("VerifyNow credentials are incomplete.")
        try:
            status, body = self._call("GET", "/auth/v1/authentication/token", {
                "customerId": settings.VERIFYNOW_CUSTOMER_ID, "key": settings.VERIFYNOW_AUTH_KEY,
                "scope": "NEW", "country": "91",
            })
        except _Unauthorised:
            raise SMSDeliveryError("VerifyNow rejected the credentials.") from None
        token = body.get("token")
        if status != 200 or not isinstance(token, str) or not token:
            raise SMSDeliveryError("VerifyNow did not issue a token.")
        cache.set(TOKEN_CACHE_KEY, token, TOKEN_CACHE_SECONDS)
        return token

    def _authorised(self, method, path, params):
        try:
            return self._call(method, path, params, self._token())
        except _Unauthorised:
            try:
                return self._call(method, path, params, self._token(refresh=True))
            except _Unauthorised:
                raise SMSDeliveryError("VerifyNow rejected the token.") from None

    def send_otp(self, phone, code):
        """Ask VerifyNow to send its own 6 digit code. Our code is not used. Returns the verificationId."""
        status, body = self._authorised("POST", "/verification/v3/send", {
            "countryCode": "91", "customerId": settings.VERIFYNOW_CUSTOMER_ID, "flowType": "SMS",
            "mobileNumber": phone.removeprefix("+91"), "otpLength": 6,
        })
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        verification_id = data.get("verificationId")
        if status != 200 or _response_code(body) != 200 or verification_id in (None, ""):
            raise SMSDeliveryError(f"VerifyNow did not accept the SMS (code {_response_code(body)}).")
        return str(verification_id)[:120]

    def check(self, reference, code):
        """Return 'ok', 'wrong' or 'expired'. Raises SMSDeliveryError if the provider cannot answer."""
        status, body = self._authorised("GET", "/verification/v3/validateOtp", {
            "verificationId": reference, "code": code, "flowType": "SMS",
            "customerId": settings.VERIFYNOW_CUSTOMER_ID,
        })
        result = _response_code(body)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        if status == 200 and result == 200 and data.get("verificationStatus") == "VERIFICATION_COMPLETED":
            return "ok"
        if result in EXPIRED_CODES:
            return "expired"
        if result in WRONG_CODES:
            return "wrong"
        raise SMSDeliveryError(f"VerifyNow could not check the code (code {result}).")
