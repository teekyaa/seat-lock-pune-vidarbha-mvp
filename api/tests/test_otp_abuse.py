"""OTP abuse limits: escalating waits, daily caps, flags, temporary blocks and the spend cap."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts import abuse
from apps.accounts.models import OTPAbuseFlag, OTPChallenge
from apps.notifications.channels import SMSDeliveryError

pytestmark = pytest.mark.django_db
PHONE = "+919876543210"
REQUEST = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def ask(client, phone="9876543210", ip="192.0.2.10", **extra):
    return client.post(REQUEST, {"phone": phone, **extra}, format="json", REMOTE_ADDR=ip)


def skip_wait(phone=PHONE):
    cache.delete(f"otp:cooldown:{phone}")


def flag(kind, value):
    return OTPAbuseFlag.objects.get(kind=kind, value=value)


def test_wait_between_codes_grows(policy):
    c = APIClient()
    waits = []
    for _ in range(3):
        r = ask(c)
        assert r.status_code == 200
        waits.append(r.data["resend_after"])
        skip_wait()
    assert waits == [60, 120, 300]


def test_asking_again_during_the_wait_is_refused_and_flagged(policy):
    c = APIClient()
    assert ask(c).status_code == 200
    r = ask(c)
    assert r.status_code == 429 and r.data["code"] == "otp_cooldown" and 1 <= r.data["retry_after"] <= 60
    f = flag("phone", PHONE)
    assert f.reason == "cooldown_ignored" and f.hits == 1 and f.blocked_until is None
    assert OTPChallenge.objects.filter(phone=PHONE).count() == 1


def test_repeated_hits_block_the_number_with_an_exact_time(policy, settings):
    settings.OTP_BLOCK_AFTER_HITS = 3
    c = APIClient()
    assert ask(c).status_code == 200
    for _ in range(2):
        assert ask(c).data["code"] == "otp_cooldown"
    r = ask(c)  # third hit (now also over the 15 minute limit) reaches the threshold and says so
    assert r.status_code == 429 and r.data["code"] == "otp_blocked"
    blocked = flag("phone", PHONE)
    assert blocked.blocked_until is not None and blocked.times_blocked == 1

    cache.clear()  # the block lives in the database, not the cache
    r = ask(c)
    assert r.status_code == 429 and r.data["code"] == "otp_blocked"
    assert "IST" in r.data["detail"] and "hours" not in r.data["detail"]
    assert r.data["blocked_until"] == blocked.blocked_until.isoformat()
    # Another number on the same network is unaffected.
    assert ask(c, phone="9876543211").status_code == 200


def test_burst_limit_hit_is_flagged(policy):
    c = APIClient()
    for _ in range(3):
        assert ask(c).status_code == 200
        skip_wait()
    r = ask(c)
    assert r.status_code == 429 and r.data["code"] == "rate_limited"
    assert flag("phone", PHONE).reason == "phone_burst"


def test_daily_cap_per_number(policy, settings):
    settings.OTP_SENDS_PER_PHONE = 100
    settings.OTP_SENDS_PER_PHONE_DAY = 2
    c = APIClient()
    for _ in range(2):
        assert ask(c).status_code == 200
        skip_wait()
    r = ask(c)
    assert r.status_code == 429 and "tomorrow" in r.data["detail"]
    assert flag("phone", PHONE).reason == "phone_daily"


def test_many_numbers_from_one_ip_is_flagged(policy, settings):
    settings.OTP_NUMBERS_PER_IP_DAY = 2
    c = APIClient()
    assert ask(c, phone="9876543210").status_code == 200
    assert ask(c, phone="9876543211").status_code == 200
    r = ask(c, phone="9876543212")
    assert r.status_code == 429 and "different numbers" in r.data["detail"]
    assert flag("ip", "192.0.2.10").reason == "ip_many_numbers"
    # The same numbers can still get codes again later; only new numbers count.
    skip_wait("+919876543210")
    assert ask(c, phone="9876543210").status_code == 200


def test_ip_blocks_are_short(policy, settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 1
    f = abuse.record_hit("ip", "192.0.2.10", "ip_burst", clock())
    assert f.blocked_until == clock() + timedelta(hours=settings.OTP_BLOCK_HOURS_IP)
    p = abuse.record_hit("phone", PHONE, "phone_burst", clock())
    assert p.blocked_until == clock() + timedelta(hours=settings.OTP_BLOCK_HOURS_PHONE)


def test_repeat_blocks_double_and_cap_at_a_week(policy, settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 1
    lengths = []
    for _ in range(5):
        f = abuse.record_hit("phone", PHONE, "phone_burst", clock())
        lengths.append(f.blocked_until - clock())
        clock.set(f.blocked_until + timedelta(minutes=1))
    assert [int(x.total_seconds() // 3600) for x in lengths] == [24, 48, 96, 168, 168]


def test_hits_reset_after_a_quiet_window(policy, settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 3
    abuse.record_hit("phone", PHONE, "cooldown_ignored", clock())
    abuse.record_hit("phone", PHONE, "cooldown_ignored", clock())
    clock.advance(hours=settings.OTP_FLAG_WINDOW_HOURS + 1)
    f = abuse.record_hit("phone", PHONE, "cooldown_ignored", clock())
    assert f.hits == 1 and f.total_hits == 3 and f.blocked_until is None


def test_block_expires_on_its_own(policy, settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 1
    f = abuse.record_hit("phone", PHONE, "phone_burst", clock())
    assert abuse.active_block("phone", PHONE, clock()) == f.blocked_until
    clock.set(f.blocked_until + timedelta(seconds=1))
    assert abuse.active_block("phone", PHONE, clock()) is None
    assert ask(APIClient()).status_code == 200


def test_global_hourly_cap_protects_the_bill(policy, settings):
    settings.OTP_GLOBAL_SENDS_PER_HOUR = 1
    c = APIClient()
    assert ask(c, phone="9876543210").status_code == 200
    r = ask(c, phone="9876543211")
    assert r.status_code == 503 and r.data["code"] == "otp_busy"
    assert cache.get("otp:cooldown:+919876543211") is None  # the person can retry once the cap clears


def test_five_wrong_codes_flag_the_number(policy, settings):
    settings.OTP_DEBUG_ECHO = True
    c = APIClient()
    code = ask(c).data["debug_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        c.post(VERIFY, {"phone": "9876543210", "code": wrong}, format="json")
    assert flag("phone", PHONE).reason == "wrong_codes"


def test_verify_burst_flags_the_ip(policy, settings):
    settings.OTP_VERIFY_ATTEMPTS_PER_IP = 1
    c = APIClient()
    c.post(VERIFY, {"phone": "9876543210", "code": "000000"}, format="json", REMOTE_ADDR="192.0.2.20")
    r = c.post(VERIFY, {"phone": "9876543210", "code": "000000"}, format="json", REMOTE_ADDR="192.0.2.20")
    assert r.status_code == 429 and flag("ip", "192.0.2.20").reason == "verify_burst"


def senders(monkeypatch, *items):
    monkeypatch.setattr("apps.accounts.otp.configured_backends", lambda: list(items))


def fake(channel, fails=False, ref="", verifies=False):
    def send(phone, code):
        if fails:
            raise SMSDeliveryError("down")
        return ref

    return SimpleNamespace(channel=channel, verifies_code=verifies, send_otp=send)


def test_response_says_which_channel_was_used(policy, monkeypatch):
    senders(monkeypatch, ("x.WhatsApp", fake("whatsapp")), ("x.SMS", fake("sms")))
    c = APIClient()
    r = ask(c)
    assert r.data["channel"] == "whatsapp" and r.data["sms_available"] is True
    skip_wait()
    r = ask(c, channel="sms")
    assert r.data["channel"] == "sms"
    assert list(OTPChallenge.objects.order_by("pk").values_list("channel", flat=True)) == ["whatsapp", "sms"]


def test_whatsapp_outage_falls_back_to_sms(policy, monkeypatch):
    senders(monkeypatch, ("x.WhatsApp", fake("whatsapp", fails=True)), ("x.SMS", fake("sms")))
    assert ask(APIClient()).data["channel"] == "sms"


def test_provider_checked_codes_sign_in(policy, monkeypatch, settings):
    settings.OTP_DEBUG_ECHO = True
    senders(monkeypatch, ("x.VerifyNow", fake("sms", ref="2949", verifies=True)))
    checks = []

    def check(backend, reference, code):
        checks.append((backend, reference, code))
        return "ok" if code == "424242" else "wrong"

    monkeypatch.setattr("apps.accounts.otp.provider_check", check)
    c = APIClient()
    r = ask(c)
    assert "debug_code" not in r.data  # we never know the provider's code
    challenge = OTPChallenge.objects.get(phone=PHONE)
    assert challenge.code_hash == "" and challenge.provider_ref == "2949" and challenge.backend == "x.VerifyNow"
    assert c.post(VERIFY, {"phone": "9876543210", "code": "111111"}, format="json").data["code"] == "otp_wrong"
    r = c.post(VERIFY, {"phone": "9876543210", "code": "424242"}, format="json")
    assert r.status_code == 200 and "token" in r.data
    assert checks == [("x.VerifyNow", "2949", "111111"), ("x.VerifyNow", "2949", "424242")]


def test_provider_outage_during_check_does_not_use_up_a_try(policy, monkeypatch):
    senders(monkeypatch, ("x.VerifyNow", fake("sms", ref="2949", verifies=True)))

    def down(backend, reference, code):
        raise SMSDeliveryError("down")

    monkeypatch.setattr("apps.accounts.otp.provider_check", down)
    c = APIClient()
    ask(c)
    r = c.post(VERIFY, {"phone": "9876543210", "code": "123456"}, format="json")
    assert r.status_code == 503 and r.data["code"] == "otp_check_unavailable"
    assert OTPChallenge.objects.get(phone=PHONE).attempts == 0


def test_non_numeric_codes_count_as_wrong_without_calling_the_provider(policy, monkeypatch):
    senders(monkeypatch, ("x.VerifyNow", fake("sms", ref="2949", verifies=True)))
    monkeypatch.setattr("apps.accounts.otp.provider_check", lambda *a: pytest.fail("provider called"))
    c = APIClient()
    ask(c)
    r = c.post(VERIFY, {"phone": "9876543210", "code": "12ab56"}, format="json")
    assert r.data["code"] == "otp_wrong" and OTPChallenge.objects.get(phone=PHONE).attempts == 1


def test_admin_unblock_lets_the_number_ask_again(policy, settings, clock):
    from django.contrib.admin.sites import site

    settings.OTP_BLOCK_AFTER_HITS = 1
    abuse.record_hit("phone", PHONE, "phone_burst", clock())
    assert ask(APIClient()).data["code"] == "otp_blocked"
    model_admin = site._registry[OTPAbuseFlag]
    model_admin.unblock(None, OTPAbuseFlag.objects.filter(value=PHONE))
    reviewed = flag("phone", PHONE)
    assert reviewed.blocked_until is None and reviewed.reviewed_at == clock()
    assert ask(APIClient()).status_code == 200


def test_admin_overview_counts_blocks_and_flags(policy, settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 1
    abuse.record_hit("phone", PHONE, "phone_burst", clock())
    settings.OTP_BLOCK_AFTER_HITS = 5
    abuse.record_hit("ip", "192.0.2.10", "ip_burst", clock())
    assert OTPAbuseFlag.objects.filter(blocked_until__gt=clock()).count() == 1
    assert OTPAbuseFlag.objects.count() == 2
