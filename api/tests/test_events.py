"""Domain events: outbox capture, relay delivery and the idempotent metrics consumer (no broker)."""
import json
import os
import uuid
from datetime import timedelta

import pytest

from apps.accounts import abuse
from apps.bookings import services
from apps.events import consumers, relay
from apps.events.models import DailyMetric, OutboxEvent, ProcessedEvent
from apps.events.outbox import TOPIC_AUTH, TOPIC_BOOKINGS, TOPIC_RIDES, emit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def outbox_on(settings):
    settings.EVENTS_OUTBOX_ENABLED = True


def types(topic=None):
    qs = OutboxEvent.objects.order_by("id")
    if topic:
        qs = qs.filter(topic=topic)
    return list(qs.values_list("type", flat=True))


def test_outbox_off_writes_nothing(settings, ride, rahul):
    settings.EVENTS_OUTBOX_ENABLED = False
    before = OutboxEvent.objects.count()  # the ride fixture was posted while events were on
    assert emit(TOPIC_RIDES, "R1", "ride.posted", "ride", "R1", {}) is None
    services.request_seat(ride, rahul, policy_ack=True)
    assert OutboxEvent.objects.count() == before


def test_booking_lifecycle_emits_ordered_events_keyed_by_ride(ride, rahul, confirm):
    booking = confirm(ride, rahul)
    assert types(TOPIC_BOOKINGS) == ["booking.requested", "booking.accepted", "booking.advance_claimed",
                                     "booking.confirmed"]
    rows = OutboxEvent.objects.filter(topic=TOPIC_BOOKINGS)
    assert set(rows.values_list("key", flat=True)) == {ride.code}  # one partition per ride: ordered history
    confirmed = rows.get(type="booking.confirmed").payload
    assert confirmed["aggregate"] == {"type": "booking", "id": booking.code}
    assert confirmed["data"]["previous_status"] == "advance_claimed"
    assert confirmed["data"]["fare_inr"] == booking.fare_inr and confirmed["version"] == 1


def test_events_never_carry_contact_details(ride, rahul, confirm):
    confirm(ride, rahul)
    services.cancel_by_passenger(rahul.bookings.get(), rahul)
    blob = json.dumps([e.payload for e in OutboxEvent.objects.all()])
    for secret in (rahul.phone, rahul.phone[3:], rahul.upi_id, ride.driver.phone, ride.driver.upi_id,
                   ride.vehicle.registration, rahul.name):
        assert secret not in blob


def test_saves_without_a_status_change_emit_nothing(ride, rahul):
    booking = services.request_seat(ride, rahul, policy_ack=True)
    before = OutboxEvent.objects.count()
    booking.note = "Window seat please"
    booking.save()
    assert OutboxEvent.objects.count() == before


def test_ride_cancel_and_reschedule_events(ride, rahul, confirm, clock):
    confirm(ride, rahul)
    services.reschedule(ride, ride.driver, ride.departure_at + timedelta(hours=3))
    services.cancel_ride(ride, ride.driver)
    assert "ride.rescheduled" in types(TOPIC_RIDES) and "ride.cancelled" in types(TOPIC_RIDES)
    assert "booking.cancelled_driver" in types(TOPIC_BOOKINGS)
    assert "trust.reliability_recorded" in types()


def test_route_ride_posting_emits_ride_posted(post_route_ride):
    ride = post_route_ride()
    posted = OutboxEvent.objects.get(type="ride.posted").payload
    assert posted["data"]["ride"] == ride.code and posted["data"]["route_id"] == ride.route_id


def test_event_rolls_back_with_its_transaction(ride, rahul):
    from django.db import transaction

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            services.request_seat(ride, rahul, policy_ack=True)
            raise RuntimeError("booking failed after the save")
    assert not OutboxEvent.objects.filter(topic=TOPIC_BOOKINGS).exists()  # no phantom event


def test_otp_block_event_hides_the_phone_number(settings, clock):
    settings.OTP_BLOCK_AFTER_HITS = 1
    flag = abuse.record_hit("phone", "+919876543210", "phone_burst", clock())
    event = OutboxEvent.objects.get(topic=TOPIC_AUTH)
    assert event.type == "auth.otp_blocked" and event.payload["data"]["flag_id"] == flag.pk
    assert "9876543210" not in json.dumps(event.payload)


class FakeProducer:
    def __init__(self, fail=()):
        self.sent, self.fail = [], set(fail)

    def produce(self, topic, key, value, event_id):
        self.sent.append((topic, key, json.loads(value)))

    def flush(self, timeout):
        return {eid: "broker down" for eid in self.fail}


def test_relay_publishes_in_order_and_marks_rows(ride, rahul, confirm, clock):
    confirm(ride, rahul)
    producer = FakeProducer()
    published, failed = relay.publish_batch(producer, clock())
    assert failed == 0 and published == OutboxEvent.objects.count()
    assert [p["type"] for _, _, p in producer.sent] == types()
    assert not OutboxEvent.objects.filter(published_at__isnull=True).exists()
    assert relay.publish_batch(producer, clock()) == (0, 0)  # nothing left to send


def test_relay_backs_off_failed_events_and_retries_later(ride, clock):
    event = emit(TOPIC_RIDES, "R1", "ride.test", "ride", "R1", {})
    producer = FakeProducer(fail={str(event.event_id)})
    assert relay.publish_batch(producer, clock())[1] >= 1
    event.refresh_from_db()
    assert event.published_at is None and event.attempts == 1 and event.last_error == "broker down"
    assert event.next_attempt_at == clock() + timedelta(seconds=2)
    # Not due yet: skipped. After the backoff, a healthy broker gets it.
    OutboxEvent.objects.exclude(pk=event.pk).update(published_at=clock())
    assert relay.publish_batch(FakeProducer(), clock()) == (0, 0)
    clock.advance(seconds=3)
    assert relay.publish_batch(FakeProducer(), clock()) == (1, 0)


def test_whole_batch_failure_keeps_every_row(ride, clock):
    for n in range(3):
        emit(TOPIC_RIDES, f"R{n}", "ride.test", "ride", f"R{n}", {})
    producer = FakeProducer()
    producer.flush = lambda timeout: {"*": "timeout"}
    published, failed = relay.publish_batch(producer, clock())
    assert published == 0 and failed == OutboxEvent.objects.count()
    assert not OutboxEvent.objects.filter(published_at__isnull=False).exists()


def test_prune_deletes_only_old_published_rows(ride, clock):
    old = emit(TOPIC_RIDES, "R1", "ride.test", "ride", "R1", {})
    pending = emit(TOPIC_RIDES, "R2", "ride.test", "ride", "R2", {})
    OutboxEvent.objects.filter(pk=old.pk).update(published_at=clock() - timedelta(days=8))
    OutboxEvent.objects.filter(pk=pending.pk).update(created_at=clock() - timedelta(days=30))
    assert relay.prune(clock(), keep_days=7) == 1
    assert OutboxEvent.objects.filter(pk=pending.pk).exists()


def envelope(event_type="booking.confirmed", occurred="2026-09-01T20:00:00+00:00", **data):
    return {"event_id": str(uuid.uuid4()), "type": event_type, "version": 1, "occurred_at": occurred,
            "aggregate": {"type": "booking", "id": "B1"}, "data": data}


def test_metrics_consumer_is_idempotent_and_uses_ist_days():
    event = envelope()  # 20:00 UTC on 1 Sep is 01:30 IST on 2 Sep
    assert consumers.apply_metrics(event) is True
    assert consumers.apply_metrics(event) is False  # replay after a crash: no double count
    metric = DailyMetric.objects.get(name="seats_confirmed")
    assert metric.count == 1 and str(metric.day) == "2026-09-02"
    consumers.apply_metrics(envelope())
    assert DailyMetric.objects.get(name="seats_confirmed").count == 2
    assert ProcessedEvent.objects.count() == 2


def test_metrics_consumer_counts_reliability_kinds_and_skips_unknown_types():
    consumers.apply_metrics(envelope("trust.reliability_recorded", kind="passenger_late_cancel"))
    assert consumers.apply_metrics(envelope("booking.something_new")) is True  # acknowledged, nothing counted
    assert list(DailyMetric.objects.values_list("name", flat=True)) == ["reliability_passenger_late_cancel"]


@pytest.mark.parametrize("raw", [b"not json", b"{}", json.dumps({"event_id": 1, "type": "x", "occurred_at": "now"}).encode()])
def test_bad_messages_are_poison_not_crashes(raw):
    with pytest.raises(consumers.PoisonMessage):
        consumers.parse(raw)


def test_end_to_end_from_service_to_metric(ride, rahul, confirm, clock):
    """The whole path without a broker: service -> outbox -> relay -> consumer -> metric."""
    confirm(ride, rahul)
    producer = FakeProducer()
    relay.publish_batch(producer, clock())
    for _, _, payload in producer.sent:
        consumers.apply_metrics(consumers.parse(json.dumps(payload).encode()))
    counts = dict(DailyMetric.objects.values_list("name", "count"))
    assert counts["seat_requests"] == 1 and counts["seats_confirmed"] == 1


@pytest.mark.skipif(not os.environ.get("KAFKA_TEST_BOOTSTRAP"), reason="needs a real Kafka broker (CI)")
def test_real_broker_round_trip(settings, ride, rahul, confirm, clock):
    """CI only: publish through a real Kafka broker and consume the events back."""
    from django.core.management import call_command

    settings.KAFKA_ENABLED = True
    settings.KAFKA_BOOTSTRAP_SERVERS = os.environ["KAFKA_TEST_BOOTSTRAP"]
    settings.KAFKA_CLIENT_ID = f"seatlock-test-{uuid.uuid4().hex[:8]}"
    call_command("create_event_topics")
    confirm(ride, rahul)
    expected = OutboxEvent.objects.count()
    published, failed = relay.publish_batch(relay.KafkaProducerAdapter(), clock(), flush_timeout=30)
    assert (published, failed) == (expected, 0)
    call_command("run_event_consumer", "--max-messages", str(expected), "--idle-timeout", "30")
    assert DailyMetric.objects.get(name="seats_confirmed").count == 1
    assert ProcessedEvent.objects.count() == expected
