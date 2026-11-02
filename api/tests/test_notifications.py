"""Scheduled messages are rows; the tick sends due rows and skips stale ones."""
from datetime import timedelta

from django.core import mail

from apps.bookings import services
from apps.notifications.dispatch import dispatch_due
from apps.notifications.models import Notification
from apps.notifications.tasks import run_tick

N = Notification.Status


def kinds_for(user):
    return set(Notification.objects.filter(user=user).values_list("kind", flat=True))


def test_confirmation_schedules_the_reminder_plan(ride, rahul, confirm):
    b = confirm(ride, rahul)
    passenger = kinds_for(rahul)
    driver = kinds_for(ride.driver)
    assert {"booking_confirmed", "still_coming_72", "reconfirm_48", "reconfirm_12", "trip_check",
            "trip_check_reminder"} <= passenger
    assert {"booking_confirmed", "reconfirm_48", "reconfirm_48_check", "reconfirm_12", "mark_no_show",
            "trip_check"} <= driver
    row = Notification.objects.get(user=rahul, kind="still_coming_72")
    assert row.send_at == ride.departure_at - timedelta(hours=72)
    assert row.booking_id == b.pk


def test_confirmation_message_shows_exact_cutoffs(ride, rahul, confirm):
    confirm(ride, rahul)
    body = Notification.objects.get(user=rahul, kind="booking_confirmed").body
    assert "IST" in body and "hours before" not in body


def test_past_reminders_are_not_scheduled(make_ride, rahul, confirm):
    ride = make_ride(hours_ahead=40)
    confirm(ride, rahul)
    assert "still_coming_72" not in kinds_for(rahul)


def test_dispatch_sends_due_and_emails(ride, rahul, confirm, clock):
    rahul.email = "rahul@example.com"
    rahul.save()
    confirm(ride, rahul)
    sent = dispatch_due(clock.now)
    assert sent >= 1
    row = Notification.objects.get(user=rahul, kind="booking_confirmed")
    assert row.status == N.SENT and "email" in row.channels_sent
    assert any(m.to == ["rahul@example.com"] for m in mail.outbox)
    assert Notification.objects.get(user=rahul, kind="still_coming_72").status == N.PENDING


def test_answered_reminder_is_skipped(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=47))
    services.reconfirm(b, rahul, 48, True)
    dispatch_due(clock.now)
    assert Notification.objects.get(user=rahul, kind="reconfirm_48").status == N.SKIPPED


def test_cancelled_booking_reminders_are_dropped(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    services.cancel_by_passenger(b, rahul)
    assert not Notification.objects.filter(user=rahul, kind="still_coming_72", status=N.PENDING).exists()


def test_unanswered_48h_flags_seat_and_alerts_waitlist(make_ride, rahul, neha, confirm, clock):
    ride = make_ride(seats=1)
    b = confirm(ride, rahul)
    services.join_waitlist(ride, neha)
    clock.set(ride.departure_at - timedelta(hours=42))
    run_tick(clock.now)
    b.refresh_from_db()
    assert b.at_risk
    assert Notification.objects.filter(user=neha, kind="waitlist_heads_up").exists()
    assert Notification.objects.filter(user=ride.driver, kind="seat_at_risk").exists()


def test_tick_is_idempotent(ride, rahul, confirm, clock):
    confirm(ride, rahul)
    run_tick(clock.now)
    before = Notification.objects.filter(status=N.SENT).count()
    run_tick(clock.now)
    assert Notification.objects.filter(status=N.SENT).count() == before


def test_failed_delivery_is_retried_without_repeating_successful_channel(rahul, clock, monkeypatch):
    attempts = []
    def email(_):
        attempts.append('email')
        if attempts.count('email') == 1:
            raise TimeoutError('sensitive provider information')
        return True
    def push(_):
        attempts.append('push')
        return True
    monkeypatch.setattr('apps.notifications.channels.send_email', email)
    monkeypatch.setattr('apps.notifications.channels.send_push', push)
    row = Notification.objects.create(user=rahul, kind='test', title='Test', send_at=clock.now)
    dispatch_due(clock.now)
    row.refresh_from_db()
    assert row.status == N.SENT and row.next_retry_at is not None
    assert 'sensitive' not in row.last_error
    assert set(row.channels_sent) == {'in_app', 'push'}
    clock.advance(minutes=1)
    dispatch_due(clock.now)
    row.refresh_from_db()
    assert row.next_retry_at is None and not row.last_error
    assert attempts == ['email', 'push', 'email']
