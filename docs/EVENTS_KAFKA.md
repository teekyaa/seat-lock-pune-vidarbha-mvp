# Domain events with Kafka (design record, 10 November 2026)

**Status:** built. Kafka carries *facts that already happened*. It is not on the booking path: a seat confirms whether or not Kafka is up.

## 1. The problem Kafka solves here

Every important change in Seat Lock is a single PostgreSQL transaction. Examples are a seat confirmed, a ride cancelled late, or a number blocked for OTP abuse. Other parts of the system want to *react* to those changes without the booking code knowing about them:

- Ops metrics (bookings confirmed per day, late cancellations, abuse blocks) without slow `COUNT(*)` scans on hot tables.
- Later, a search index for stops along the way (route network Phase 2), a WhatsApp group bot that posts new rides, or a warehouse for the Diwali concierge analysis.

Calling each of those from inside `services.py` couples them to booking latency and failures. A booking would fail because the analytics service is down. Kafka turns this into **publish once, many independent readers**, each with its own pace and its own position in the log.

## 2. What Kafka is *not* used for, and why

| Job | Stays on | Reason |
| --- | --- | --- |
| Seat counts, holds, confirmations | PostgreSQL row locks | Needs a strongly consistent answer *now*. A log is eventually consistent. |
| Reminders at 72 h, 48 h, 12 h; hold expiry | `notifications` rows + per-minute tick | Kafka has no "deliver at time T". Delayed delivery on Kafka means extra topics and polling, which is worse than a row with `due_at`. CLAUDE.md keeps "scheduled messages are rows". |
| OTP rate limits, cache | Redis | Tiny, hot, expiring counters are what Redis is built for. |

**Interview line:** "I didn't replace the database with Kafka. I used the database for decisions and Kafka for distributing the decisions."

## 3. The dual-write problem and the transactional outbox

The naive version is "commit the booking, then `producer.send()`". That has two failure modes:

1. The commit succeeds and the process dies before the send: **the event is lost**.
2. The send succeeds and the commit rolls back: **an event for something that never happened**.

You can't make PostgreSQL and Kafka commit atomically together, because there are no distributed transactions here. The fix is the **transactional outbox**:

```text
service function (one DB transaction)
  ├─ UPDATE bookings SET status='confirmed' ...
  └─ INSERT INTO events_outbox (event_id, topic, key, type, payload) ...
COMMIT  ← both or neither

relay process (separate, loops every second)
  SELECT ... FROM events_outbox WHERE published_at IS NULL
    ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 100
  produce to Kafka (acks=all, idempotent producer) → flush
  UPDATE events_outbox SET published_at = now()
```

- **At-least-once:** if the relay crashes after Kafka acks but before marking the rows, it publishes them again. Duplicates are possible; loss is not.
- **`SKIP LOCKED`:** a second relay copy can run without double-sending in-flight rows. It's the same trick the notification dispatcher already uses.
- **Backoff:** a failed batch increments `attempts` and pushes `next_attempt_at` out (2^n seconds, capped at 5 minutes). Kafka being down only delays events; bookings are unaffected.

## 4. Consumers must be idempotent (effectively-once)

Because delivery is at-least-once, every consumer de-duplicates on `event_id`:

```text
poll message → BEGIN
  INSERT INTO events_processed (consumer, event_id)   -- unique; conflict = duplicate → skip
  apply the effect (e.g. UPDATE events_dailymetric SET count = count + 1)
COMMIT → commit the Kafka offset
```

The offset is committed **after** the DB commit. A crash between the two replays the message, and the unique row turns the replay into a no-op. That's how "exactly once" is usually achieved in practice: **at-least-once delivery plus an idempotent consumer**.

## 5. Topics, keys and ordering

| Topic | Key | Events |
| --- | --- | --- |
| `seatlock.bookings.v1` | ride code | requested, accepted, declined, advance_claimed, confirmed, cancelled_by_passenger, no_show_marked, trip_confirmed |
| `seatlock.rides.v1` | ride code | posted, cancelled, rescheduled |
| `seatlock.trust.v1` | user id | reliability_recorded |
| `seatlock.auth.v1` | flag id | otp_blocked |

- Kafka only orders messages **within a partition**, and the key picks the partition. Keying bookings by **ride code** means everything about one ride is read in order: requested, then confirmed, then cancelled. Different rides spread across partitions and process in parallel.
- 3 partitions per topic: enough parallelism for this scale, and the count can grow later. Growing it remaps keys, so do it before consumers depend on ordering across a resize.
- `.v1` in the name and `"version": 1` in the envelope: a breaking schema change ships as `v2` alongside `v1`, and consumers migrate on their own schedule.

## 6. Event envelope and privacy

```json
{"event_id": "uuid", "type": "booking.confirmed", "version": 1,
 "occurred_at": "2026-11-10T06:00:00Z", "aggregate": {"type": "booking", "id": "SL-7Q2K"},
 "data": {"ride": "R-ABCD", "seat_role": "passenger", "fare_inr": 1450, "advance_inr": 450}}
```

Events carry ids, codes, statuses and integer rupees only. **No phone numbers, UPI IDs, names or registrations** (hard rule 3). A log is copied, retained and replayed, so treat it as "will leak eventually" and keep it boring. Phone numbers in OTP flags never leave the database; the event carries the flag id and reason.

## 7. Running it on one free VM

- Single-node Apache Kafka in **KRaft mode** (no ZooKeeper), heap capped at 512 MB, 7-day retention, replication factor 1. This is honest single-node durability: the disk is the durability, and the outbox table is the source of truth for re-publishing.
- `KAFKA_ENABLED=0` (the default locally) makes `emit()` a no-op, so development and the existing tests need no broker. CI runs one integration test against a real broker.
- Processes: `relay` (outbox to Kafka) and `consumer-metrics` (Kafka to the daily metrics table) are separate containers, so either can restart without touching the web or API.

## 8. Trade-offs to state out loud

- **Cost:** one more stateful service to run, upgrade and monitor, and about 1 GB of RAM on a 12 GB box. At a few hundred users a PostgreSQL `LISTEN/NOTIFY` or Redis Streams would also work. Kafka is chosen for replayable, multi-consumer history and to learn the industry-standard tool, and this record says so.
- **Latency:** events arrive within about 1 to 2 seconds (relay poll), which is fine for metrics and bots. Anything that needs read-your-writes stays on PostgreSQL.
- **Outbox growth:** published rows are pruned after 7 days by the scheduler tick.

## 9. How to explain it in an interview (60 seconds)

> "Bookings are strongly consistent in Postgres with row locks. Downstream reactions such as analytics and bots shouldn't be able to slow down or break a booking, so state changes write an event to an outbox table in the same transaction. A relay publishes the outbox to Kafka with an idempotent producer, which gives at-least-once delivery with no lost or phantom events. Consumers de-duplicate by event id inside their own DB transaction and commit offsets after, which makes processing effectively-once. Topics are keyed by ride so each ride's history is ordered. Scheduled reminders deliberately stay as database rows, because Kafka has no delayed delivery."
