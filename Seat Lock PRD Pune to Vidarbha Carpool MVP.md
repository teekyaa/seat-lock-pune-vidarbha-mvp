# Seat Lock PRD: Pune to Vidarbha Carpool MVP

Oct 27, 2026 · @rohan

## Overview

Seat Lock (working title) is a mobile web app for cost-sharing carpools between Pune and Vidarbha that cuts last-minute cancellations by locking every seat with a UPI advance under a time-based refund policy. The MVP targets one corridor, festival-season travel, and never holds money.

### Problem

Pune to Nagpur, Wardha and Chandrapur travel is arranged today in WhatsApp groups through free-form posts and private DMs. Drivers lose co-drivers and passengers hours before a 12 to 16 hour drive, and passengers who pay advances have no protection when drivers cancel. Nobody can see whether the person they are about to ride with has a history of showing up.

### What we are building

A place to post and book carpool seats where both sides agree to one clear cancellation policy, the passenger pays a refundable-by-schedule advance directly to the driver over UPI, freed seats are offered to a waitlist, and every cancellation builds a public reliability record. Rides are shared back into WhatsApp groups as clean cards, so the app works alongside the groups instead of replacing them.

### Goals

1. Reduce late cancellations (under 48 hours before departure) compared with what drivers experience in the WhatsApp groups today.
2. Get every posted ride to at least one confirmed passenger quickly enough that drivers keep posting here.
3. Keep every ride within cost-sharing limits so drivers stay on the right side of Maharashtra carpool rules.

### Non-goals

- Train ticket resale or transfer of any kind.
- Holding, routing or taking a commission on payments.
- Daily commute pooling or routes outside Pune and Vidarbha.

### Success metrics

Targets below are provisional. Replace them with real baselines after the Diwali concierge test.

| Metric | Definition | Provisional target |
| --- | --- | --- |
| Late cancellation rate | Confirmed bookings cancelled by either side under 48 hours before departure, divided by all confirmed bookings | Half of the baseline measured in the concierge test |
| Ride activation | Posted rides with at least one confirmed passenger within 24 hours of posting | 50% of rides |
| Refill rate | Seats freed by a cancellation that are refilled from the waitlist before departure | 40% of freed seats |
| Refund disputes | Refunds owed under the policy still unconfirmed 24 hours after they fall due | Under 5% of refunds owed |
| Driver return | Drivers from one festival window who post again in the next one | 40% of drivers |
| Trip confirmation | Completed trips where both sides answer the post-trip check | 70% of trips |

## Users

The owner-driver is the primary user: seats are scarce in festival season and passengers follow wherever drivers post.

| Persona | Who they are | What they need from Seat Lock | What makes them leave |
| --- | --- | --- | --- |
| Owner-driver (primary) | Working professional in Pune driving home to Vidarbha for festivals; wants to split fuel and tolls, not earn | Passengers who show up, a co-driver who does not bail, compensation when someone cancels late | No-shows with no consequence, haggling over fares, a passenger list that empties on the last day |
| Passenger | Student or early-career professional from Vidarbha studying or working in Pune; trains full, buses expensive | A confirmed seat with someone trustworthy, protection if the driver cancels, rules that feel fair | Paying an advance to a stranger with no recourse, rides vanishing hours before departure |
| Co-driver | A passenger who also holds a driving licence and agrees to share the wheel | Clear expectations, often a reduced fare | Being treated as an ordinary passenger, unclear duties |
| Group admin | Runs a Pune to Vidarbha WhatsApp group and keeps it on-topic | Less clutter, fewer scams, a safer group | An app that looks like spam or competes with the group |

The app is built for phones first. Most users arrive from a WhatsApp link and expect to finish signup and a booking in a few minutes.

## Cancellation and advance policy

A seat is locked when the passenger pays an advance of about 30% of the fare to the driver over UPI; cancelling early is free, cancelling late costs the advance, and a refilled seat always means a full refund. Every booking stores the policy version it was confirmed under, so later changes never apply retroactively.

### Advance

- Amount: 30% of the seat fare, rounded to the nearest ₹50, with a floor of ₹300 and a ceiling of ₹1,000. All three values live in the policy table and can change between festival seasons.
- Paid directly from passenger to driver through a UPI deep link. The app records the payment; it never receives or holds money.
- The seat is confirmed only after the driver taps "Advance received". Unpaid seat holds expire after 2 hours.

### When the passenger cancels

| Timing (before scheduled departure) | Advance outcome |
| --- | --- |
| More than 48 hours | Full refund, due within 24 hours |
| 48 to 12 hours | Driver keeps half |
| Under 12 hours, or no-show | Driver keeps all of it |
| Seat refilled by anyone before departure | Full refund, whatever the timing |

For cancellations in the two penalty tiers, the outcome is decided at departure time or when the seat is refilled, whichever comes first. Until then the passenger sees "Refund depends on whether your seat is refilled".

### When the driver cancels

| Timing (before scheduled departure) | What happens |
| --- | --- |
| Any time | Every passenger's advance is refunded in full, due within 24 hours |
| Under 48 hours | Late cancellation appears on the driver's public record, and affected passengers get first access to other rides on the same date |
| Second late cancellation in one festival season | Driver cannot post rides for the rest of that season |

If a driver moves the departure time by more than 2 hours after a seat is confirmed, every passenger may cancel with a full refund, and it counts as a driver change on the record.

### No-shows and disputes

- The driver can mark a no-show from 30 minutes after scheduled departure. The passenger gets 24 hours to dispute it.
- When a refund falls due, the passenger confirms it with "Refund received". A refund still unconfirmed 24 hours after it is due shows on the driver's profile as an open dispute until resolved.
- Disputes are reviewed by hand in the MVP. If they exceed 5% of refunds owed, escrow moves into scope for v2.

### Co-drivers

A co-driver books like any passenger and follows the same policy. Late cancellations by a co-driver are labelled as such on their record, because they cost the driver more than an empty seat.

### Fair fare

The app suggests a cost-sharing fare per seat and lets the driver go at most 15% above it, so rides stay clearly non-commercial. Distance and tolls come from a fixed table of city pairs on the corridor.

```latex
\text{suggested fare} = \frac{\text{distance (km)} \times \text{fuel cost per km (₹)} + \text{tolls (₹)}}{\text{seats offered} + 1}
```

The +1 counts the driver's own share. The 15% margin is provisional until checked against the Maharashtra carpool fare rules.

## Scope

The MVP ships posting, booking, the advance policy, reconfirmation, the waitlist and the reliability record; everything that touches money flow, live tracking or new routes waits.

**Must have**

- Phone OTP signup and a profile with name, photo, hometown, college or workplace, and gender (for women-only rides).
- Ride posting with route, departure time, seats, car, co-driver toggle and fair fare suggestion.
- WhatsApp share card for every ride.
- Ride search by direction and date.
- Seat request, driver acceptance, and policy agreement by both sides.
- UPI advance via deep link, with "Advance received" and "Refund received" confirmations.
- Cancellation tiers with exact cutoff times shown in IST.
- Reconfirmation at 72, 48 and 12 hours, with at-risk flags.
- Waitlist with automatic offers when a seat frees up.
- Reliability record and post-trip confirmation.
- Contact details revealed only after confirmation.
- Women-only ride option, report and block.

**Should have**

- Passenger "seat wanted" posts and alerts for matching rides.
- Vouching between members.
- Optional ID verification badge.
- Trip sharing with an emergency contact.

**Could have**

- Group admin page and admin-verified badge.
- Hindi and Marathi interface.
- Installable PWA with web push.
- Short written reviews.

**Won't have in the MVP**

- Train ticket resale or transfer.
- Escrow, in-app payments or commissions.
- In-app chat, live GPS tracking, native apps.
- Other corridors, commute pooling, smart matching, dynamic pricing.

## User stories

22 Must-have stories make up the launchable MVP; the 5 below them follow in the weeks after launch. Acceptance criteria are written so each story can be tested on its own.

| ID | Epic | Story | Acceptance criteria | Priority |
| --- | --- | --- | --- | --- |
| US-01 | Onboarding | As a new user arriving from a WhatsApp link, I want to sign up with my phone number and an OTP, so I can book or post without a password. | OTP by SMS, valid 5 minutes, 3 attempts per 15 minutes. After signup the user lands back on the ride they opened. | Must |
| US-02 | Onboarding | As any user, I want to add my hometown, college or workplace and a photo, so strangers can see what we have in common. | Name and photo required before the first post or booking. Hometown picked from corridor cities or "Other". | Must |
| US-03 | Onboarding | As a driver, I want to save my car and UPI ID once, so every ride and advance uses them. | UPI ID format validated. Registration number shown to passengers only after confirmation. | Must |
| US-04 | Posting | As a driver, I want to post a ride with route, departure time, seats and car, so passengers can find it. | Departure at least 6 hours ahead. Seats capped by the car's capacity. Women-only and co-driver toggles available. | Must |
| US-05 | Posting | As a driver, I want a suggested fare, so I can price fairly without arguments. | Suggested fare shown from the city-pair table. Fares more than 15% above it are blocked with an explanation. | Must |
| US-06 | Posting | As a driver, I want a share card for WhatsApp, so I can post my ride in the group in one tap. | Opens the WhatsApp share sheet with formatted text and a link. The link preview shows route, date and seats left. | Must |
| US-07 | Booking | As a passenger, I want to search rides by direction and date, so I find a seat quickly. | Results sorted by departure time, showing seats left, fare and the driver's reliability summary. Women-only rides appear only to women. | Must |
| US-08 | Booking | As a passenger, I want to request a seat with a short note, so the driver knows who I am. | One active request per ride per passenger. The driver sees the passenger's profile and record with the request. | Must |
| US-09 | Booking | As a driver, I want to accept or decline requests, so I choose who rides with me. | Acceptance opens the policy agreement for both sides. Unanswered requests expire after 12 hours, or 12 hours before departure if sooner. | Must |
| US-10 | Advance | As a passenger, I want to pay the advance through my own UPI app, so I don't have to type details. | Deep link prefilled with the driver's UPI ID, amount and booking code. "I've paid" accepts an optional UTR. Unpaid holds expire after 2 hours. | Must |
| US-11 | Advance | As a driver, I want to confirm the advance arrived, so the seat locks. | Only the driver can confirm. Seats left drops on confirmation. Both sides see exact cutoff times in IST. | Must |
| US-12 | Cancellation | As a passenger, I want to see exactly what I lose if I cancel now, so I decide early. | The cancel screen shows the current tier, the amount at stake and the refill rule before the final tap. | Must |
| US-13 | Cancellation | As a driver, I want to cancel my ride when I must, with passengers told straight away. | All passengers notified at once. Refunds marked due. A late cancellation is recorded, and a second in one season blocks posting. | Must |
| US-14 | Cancellation | As a passenger, I want to confirm a refund arrived, so unpaid refunds are visible. | Due date shown on the booking. Unconfirmed 24 hours after the due date shows as an open dispute on the driver's profile. | Must |
| US-15 | Cancellation | As a driver, I want to mark a no-show, so I keep the advance fairly. | Available from 30 minutes after departure. The passenger can dispute it for 24 hours. | Must |
| US-16 | Reconfirmation | As a driver, I want passengers to reconfirm 48 hours out, so I find out about changed plans early. | Messages at 72, 48 and 12 hours. No reply 6 hours after the 48-hour message flags the seat as at risk and alerts the waitlist. | Must |
| US-17 | Waitlist | As a passenger, I want to join the waitlist on a full ride, so I get a seat if one opens. | First come, first served. An offer is held 2 hours, or 30 minutes when under 12 hours to departure. Accepting starts the advance flow. | Must |
| US-18 | Waitlist | As a passenger who cancelled late, I want a full refund if my seat is refilled, so I lose nothing when the driver loses nothing. | The refill booking is linked to the cancelled one. The refund becomes due automatically once the new advance is confirmed. | Must |
| US-19 | Safety | As a woman passenger, I want women-only rides, so I can travel comfortably with strangers. | Only women drivers can post women-only rides, and only women can request them. | Must |
| US-20 | Safety | As any user, I want to report or block someone, so bad actors are dealt with. | Report reasons from a fixed list plus details. Blocked users cannot see or request each other's rides. Reports reviewed within 24 hours. | Must |
| US-21 | Trust | As any user, I want to see someone's reliability record, so I can judge a stranger. | Shows completed trips, early and late cancellations with hours before departure, and open disputes. Accounts with no trips show "New member". | Must |
| US-22 | Trust | As a driver or passenger, I want to confirm the trip happened, so records stay honest. | Both sides asked after the expected arrival time. Conflicting answers are flagged for review and left off the record until resolved. | Must |
| US-23 | Booking | As a passenger, I want to post "seat wanted" and get alerts for matching rides, so I don't have to keep checking. | Alert by email or web push when a ride matches direction and date within the passenger's flexibility window. | Should |
| US-24 | Trust | As a member, I want to vouch for someone I know, so new members can borrow my trust. | Up to 5 active vouches each. A vouchee's late cancellation appears on the voucher's profile. Vouches can be withdrawn. | Should |
| US-25 | Trust | As any user, I want an ID verification badge, so others know I am who I say I am. | Verified through a DigiLocker-based provider. Only the result and date are stored, never the ID number. | Should |
| US-26 | Safety | As a passenger, I want to share my trip with an emergency contact, so someone knows where I am. | Link shows driver, car, route and departure time. Expires 24 hours after expected arrival. | Should |
| US-27 | Community | As a group admin, I want a page listing upcoming rides for my group, so I can pin one link instead of moderating posts. | Admin gets a group link and can mark members as admin-verified. | Could |

## Core flows

The Aha! moment for a driver is the confirmation screen: "Seat locked. Rahul paid ₹750. If he cancels after Thursday 7 PM, you keep it." For a passenger it is knowing that a driver cancellation, or a refilled seat after their own cancellation, means a full refund.

### Driver: first ride

1. Opens a link from the WhatsApp group and signs up with phone OTP.
2. Completes the profile, adds the car and UPI ID.
3. Posts a ride; the fair fare suggestion and policy attach automatically.
4. Shares the ride card back into the WhatsApp group.
5. Reviews a seat request with the passenger's profile and record, then accepts.
6. Receives the advance in their UPI app and taps "Advance received". The seat locks and both see the cutoff times.
7. Gets reconfirmations at 72, 48 and 12 hours, plus at-risk flags if a passenger goes quiet.
8. Drives, then confirms the trip happened.

### Passenger: first booking

1. Taps a ride card in the WhatsApp group and sees the ride and the driver's record.
2. Signs up with phone OTP and adds a photo and hometown.
3. Requests a seat with a short note.
4. On acceptance, reads the policy with exact cutoff times and agrees.
5. Pays the advance through the UPI deep link and taps "I've paid".
6. Sees the seat confirmed and the driver's contact details unlock.
7. Reconfirms at 72 and 48 hours, receives pickup details at 12 hours.
8. Travels, then confirms the trip happened.

### Notification schedule

All times are relative to scheduled departure. Channels are SMS for OTP, and email plus web push for everything else in the MVP.

| When | Who | Message | Action required | If ignored |
| --- | --- | --- | --- | --- |
| On confirmation | Both | Seat locked, with exact cutoff times in IST | None | Not applicable |
| 72 hours | Passenger | Free cancellation ends in 24 hours. Still coming? | Tap "Still coming" or cancel | Repeated in the 48-hour message |
| 48 hours | Both | Reconfirm the trip | Tap to reconfirm | After 6 hours: seat marked at risk for the driver, waitlist told a seat may open |
| 12 hours | Both | Final check plus pickup point, car number and phone numbers | Tap to reconfirm | Driver can call the passenger directly; no automatic action |
| Departure | Passenger | Trip sharing link for an emergency contact | Optional | None |
| Departure + 30 min | Driver | Mark any no-show | Optional | None |
| Expected arrival | Both | Did this trip happen? | Yes or No | Reminder after 24 hours, then the trip is left unconfirmed |
| Refund due + 24 hours | Passenger | Did you receive your refund? | Tap "Refund received" | Open dispute shown on the driver's profile |

## Database schema

The schema centres on bookings: each booking carries its own policy version, cutoff timestamps and status, and every money movement and reliability change hangs off it. PostgreSQL, UUID keys, all timestamps stored in UTC and shown in IST.

| Table | Purpose | Key relations |
| --- | --- | --- |
| users | Profile, contact, UPI ID, verification and posting status | One per phone number |
| vehicles | Driver's car and passenger capacity | users 1 to many |
| city\_pairs | Fixed corridor table of distance and tolls for fare suggestions | Referenced by rides and seat\_wanted |
| policy\_versions | Advance percentage, limits, cutoff hours, fuel cost, fare margin | Referenced by every booking |
| seasons | Festival windows used for the two-strike posting rule | Referenced by reliability\_events |
| rides | A posted trip with departure time, seats, fare and toggles | users, vehicles, city\_pairs |
| bookings | One person's seat on one ride, with status, cutoffs and refund outcome | rides, users, policy\_versions, self-link for refills |
| payments | Recorded advances and refunds (records only, no money held) | bookings 1 to many |
| waitlist\_entries | Queue of passengers waiting on a full ride | rides, users |
| trip\_confirmations | Each side's answer to "Did this trip happen?" | bookings, users |
| reliability\_events | Append-only log of completed trips, cancellations, no-shows and overdue refunds | users, bookings, seasons |
| vouches, reports, blocks | Trust and safety records | users |
| seat\_wanted | Passenger requests for a seat on a date | users, city\_pairs |
| notifications | Scheduled and sent messages, with when the user acted | users, bookings |
| audit\_log | Every state change on bookings, payments and reports | Any table |

The public reliability record is a materialised view over reliability\_events, refreshed when an event is written. Events are never edited; a resolved dispute writes a correcting event.

```sql
-- Enums
CREATE TYPE gender_t        AS ENUM ('female','male','other','undisclosed');
CREATE TYPE ride_status     AS ENUM ('open','full','cancelled','departed','completed');
CREATE TYPE booking_role    AS ENUM ('passenger','co_driver');
CREATE TYPE booking_status  AS ENUM ('requested','declined','expired','accepted','advance_claimed',
                                     'confirmed','cancelled_passenger','cancelled_driver','no_show','completed');
CREATE TYPE refund_outcome  AS ENUM ('full','half','none','pending_refill');
CREATE TYPE payment_kind    AS ENUM ('advance','refund');
CREATE TYPE payment_status  AS ENUM ('due','claimed','confirmed','disputed','waived');
CREATE TYPE waitlist_status AS ENUM ('waiting','offered','accepted','expired','withdrawn');
CREATE TYPE reliability_kind AS ENUM ('trip_completed','early_cancel','late_cancel','no_show',
                                      'driver_change','refund_overdue','correction');

CREATE TABLE users (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  phone                text UNIQUE NOT NULL,
  phone_verified_at    timestamptz,
  full_name            text,
  photo_url            text,
  gender               gender_t DEFAULT 'undisclosed',
  hometown             text,
  org_name             text,
  org_kind             text CHECK (org_kind IN ('college','workplace')),
  upi_id               text,
  emergency_name       text,
  emergency_phone      text,
  id_verified_at       timestamptz,          -- result only, never the ID number
  admin_verified_by    uuid REFERENCES users(id),
  posting_blocked_until timestamptz,
  status               text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
  created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vehicles (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id           uuid NOT NULL REFERENCES users(id),
  make_model         text NOT NULL,
  colour             text,
  reg_number         text NOT NULL,
  passenger_capacity smallint NOT NULL CHECK (passenger_capacity BETWEEN 1 AND 7)
);

CREATE TABLE city_pairs (
  id          serial PRIMARY KEY,
  origin_city text NOT NULL,
  dest_city   text NOT NULL,
  distance_km int  NOT NULL,
  toll_inr    int  NOT NULL,
  UNIQUE (origin_city, dest_city)
);

CREATE TABLE policy_versions (
  id                    serial PRIMARY KEY,
  version               int UNIQUE NOT NULL,
  advance_pct           numeric(4,2) NOT NULL DEFAULT 0.30,
  advance_min_inr       int NOT NULL DEFAULT 300,
  advance_max_inr       int NOT NULL DEFAULT 1000,
  free_cancel_hours     int NOT NULL DEFAULT 48,
  full_penalty_hours    int NOT NULL DEFAULT 12,
  fuel_cost_per_km_inr  numeric(5,2) NOT NULL,
  max_fare_markup_pct   numeric(4,2) NOT NULL DEFAULT 0.15,
  policy_text_md        text NOT NULL,
  effective_from        timestamptz NOT NULL
);

CREATE TABLE seasons (
  id        serial PRIMARY KEY,
  name      text NOT NULL,                   -- e.g. 'Diwali 2026'
  starts_on date NOT NULL,
  ends_on   date NOT NULL
);

CREATE TABLE rides (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_id           uuid NOT NULL REFERENCES users(id),
  vehicle_id          uuid NOT NULL REFERENCES vehicles(id),
  city_pair_id        int  NOT NULL REFERENCES city_pairs(id),
  route_via           text,
  pickup_point        text,
  departure_at        timestamptz NOT NULL,
  expected_arrival_at timestamptz NOT NULL,
  seats_offered       smallint NOT NULL,
  fare_inr            int NOT NULL,
  suggested_fare_inr  int NOT NULL,
  women_only          boolean NOT NULL DEFAULT false,
  codriver_wanted     boolean NOT NULL DEFAULT false,
  notes               text,
  status              ride_status NOT NULL DEFAULT 'open',
  share_slug          text UNIQUE NOT NULL,
  cancelled_at        timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX rides_search ON rides (city_pair_id, departure_at) WHERE status IN ('open','full');

CREATE TABLE bookings (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id                uuid NOT NULL REFERENCES rides(id),
  passenger_id           uuid NOT NULL REFERENCES users(id),
  role                   booking_role NOT NULL DEFAULT 'passenger',
  status                 booking_status NOT NULL DEFAULT 'requested',
  note                   text,
  fare_inr               int NOT NULL,
  advance_inr            int NOT NULL,
  policy_version_id      int NOT NULL REFERENCES policy_versions(id),
  free_cancel_until      timestamptz NOT NULL,   -- departure minus free_cancel_hours
  full_penalty_from      timestamptz NOT NULL,   -- departure minus full_penalty_hours
  hold_expires_at        timestamptz,
  accepted_at            timestamptz,
  confirmed_at           timestamptz,
  reconfirmed_48h_at     timestamptz,
  reconfirmed_12h_at     timestamptz,
  at_risk_since          timestamptz,
  cancelled_at           timestamptz,
  cancelled_by           uuid REFERENCES users(id),
  hours_before_departure numeric(6,2),
  refund_outcome         refund_outcome,
  refilled_by_booking_id uuid REFERENCES bookings(id),
  created_at             timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_live_booking ON bookings (ride_id, passenger_id)
  WHERE status IN ('requested','accepted','advance_claimed','confirmed');

CREATE TABLE payments (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id   uuid NOT NULL REFERENCES bookings(id),
  kind         payment_kind NOT NULL,
  amount_inr   int NOT NULL,
  status       payment_status NOT NULL DEFAULT 'due',
  utr          text,                           -- optional UPI reference
  due_at       timestamptz,
  claimed_at   timestamptz,                    -- payer says sent
  confirmed_at timestamptz,                    -- receiver says received
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE waitlist_entries (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id          uuid NOT NULL REFERENCES rides(id),
  passenger_id     uuid NOT NULL REFERENCES users(id),
  status           waitlist_status NOT NULL DEFAULT 'waiting',
  offered_at       timestamptz,
  offer_expires_at timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ride_id, passenger_id)
);

CREATE TABLE trip_confirmations (
  booking_id   uuid REFERENCES bookings(id),
  user_id      uuid REFERENCES users(id),
  happened     boolean NOT NULL,
  responded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (booking_id, user_id)
);

CREATE TABLE reliability_events (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                uuid NOT NULL REFERENCES users(id),
  booking_id             uuid REFERENCES bookings(id),
  season_id              int REFERENCES seasons(id),
  kind                   reliability_kind NOT NULL,
  hours_before_departure numeric(6,2),
  occurred_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vouches (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  voucher_id   uuid NOT NULL REFERENCES users(id),
  vouchee_id   uuid NOT NULL REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  withdrawn_at timestamptz
);

CREATE TABLE reports (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id uuid NOT NULL REFERENCES users(id),
  reported_id uuid NOT NULL REFERENCES users(id),
  booking_id  uuid REFERENCES bookings(id),
  reason      text NOT NULL,
  details     text,
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open','actioned','dismissed')),
  resolved_at timestamptz
);

CREATE TABLE blocks (
  blocker_id uuid REFERENCES users(id),
  blocked_id uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (blocker_id, blocked_id)
);

CREATE TABLE seat_wanted (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  passenger_id uuid NOT NULL REFERENCES users(id),
  city_pair_id int  NOT NULL REFERENCES city_pairs(id),
  travel_date  date NOT NULL,
  flex_days    smallint NOT NULL DEFAULT 0,
  status       text NOT NULL DEFAULT 'active',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id),
  booking_id    uuid REFERENCES bookings(id),
  kind          text NOT NULL,                 -- e.g. 'reconfirm_48h'
  channel       text NOT NULL,                 -- 'sms','email','push'
  scheduled_for timestamptz NOT NULL,
  sent_at       timestamptz,
  acted_at      timestamptz
);

CREATE TABLE audit_log (
  id         bigserial PRIMARY KEY,
  actor_id   uuid REFERENCES users(id),
  entity     text NOT NULL,
  entity_id  uuid NOT NULL,
  action     text NOT NULL,
  data       jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

### Booking lifecycle

&#91;embedded content: booking lifecycle · 5 statuses, 5 exits\]

Only a confirmed booking counts against the ride's seats and can earn a reliability event; earlier exits leave no mark on anyone's record.

## Tech stack and architecture

Build a modular monolith: Next.js on Vercel for the web app, Django with a Celery worker on Railway for the API and scheduled jobs, PostgreSQL and Redis underneath. One developer can build and run it, and every piece scales horizontally when festival traffic spikes.

&#91;embedded content: system architecture · web, API, stores, workers\]

The worker also reads due rows from the notifications table in PostgreSQL every minute; photos upload to object storage through signed URLs issued by the API.

| Layer | Choice | Why |
| --- | --- | --- |
| Web app | Next.js (App Router), TypeScript, Tailwind, installable PWA | Server-rendered ride pages give WhatsApp rich link previews; one codebase for phone and desktop |
| Share previews | Generated Open Graph images per ride | The ride card in WhatsApp shows route, date and seats left without opening the app |
| API | Django with Django REST Framework | The built-in admin covers dispute review, reports and admin verification with no extra build; mature migrations and auth |
| Scheduled jobs | Celery worker plus Celery beat, Redis as broker | Reconfirmations, hold expiry, waitlist offers and refund checks all run on time |
| Database | PostgreSQL 16 | Partial indexes, enums, materialised views and row locking for seat counts |
| Cache and limits | Redis | OTP rate limits, session cache, Celery broker |
| SMS | An Indian SMS provider with DLT-registered OTP templates | Indian regulations require registered templates for transactional SMS |
| Email and push | Transactional email service plus Web Push (VAPID) | Cheap, no template approvals, works on Android Chrome |
| Payments | UPI deep links generated server-side (upi://pay with payee, amount, note) | No gateway, no money held, no payment aggregator obligations |
| Photos | S3-compatible object storage with resizing on upload | Keeps the database small; photos served through a CDN |
| ID verification (Should) | DigiLocker through a licensed KYC provider | Stores only the result and date, never the ID number |
| Monitoring | Sentry for errors, a product analytics tool for funnel metrics | The success metrics need event tracking from day one |
| Hosting | Vercel (web), Railway (API, worker, beat, PostgreSQL, Redis) | Push-to-deploy, low fixed cost, easy to scale the API and worker separately |

### How the scheduled jobs stay reliable

Reminders and expiries are never fired as one-off delayed tasks, because those can be lost on a restart. Every scheduled message is a row in the notifications table. A Celery beat task runs every minute, claims due rows with `SELECT … FOR UPDATE SKIP LOCKED`, sends them, and marks them sent. A restart only delays messages by a minute.

### How seat counts stay correct

Confirming an advance or accepting a waitlist offer locks the ride row, counts confirmed bookings, and confirms only if a seat is free, all in one transaction. Two passengers can never confirm the last seat at the same time.

### Scaling path

A festival peak on one corridor is a few thousand users, which this setup handles comfortably. When it grows: add API and worker containers, add a PostgreSQL read replica for search, and move ride search to a cached endpoint. Splitting into services is only worth it once there are several corridors and more than one developer.

FastAPI is a reasonable alternative for the API if async performance matters more than a ready-made admin panel, but the admin is doing real work here, so Django is the better fit for the MVP.

## Non-functional requirements

Phone numbers, car numbers and UPI IDs stay hidden until a seat is confirmed, the app never holds money, and every ride stays inside cost-sharing limits.

| Area | Requirement |
| --- | --- |
| Privacy | Phone numbers, UPI IDs and car registration shown only to confirmed co-travellers. Collect only what a feature needs, with consent at signup in line with India's Digital Personal Data Protection Act, 2023. Users can export and delete their data; reliability events are kept in anonymised form after deletion. |
| Identity data | Never store Aadhaar or other ID numbers. Store only the verification result, provider and date. |
| Security | OTP rate limits per phone and per IP. Short-lived access tokens with refresh rotation. Role checks on every booking action, so only the driver can confirm an advance and only the passenger can confirm a refund. All traffic over HTTPS. |
| Money | The app generates UPI links and records claims. It never receives, holds or splits funds, and takes no commission in the MVP. |
| Legal | Fares capped at the suggested cost-sharing fare plus 15%. Ride limits per driver tracked so the platform can enforce weekly caps if the Maharashtra carpool rules require them. Terms state that drivers share costs and do not offer a commercial service. A lawyer should review the terms and fare rule before public launch. |
| Safety | Women-only rides, report and block from launch. Reports reviewed within 24 hours, with an emergency contact share as a fast follow. |
| Performance | Ride search under 500 ms at the 95th percentile. Ride pages render server-side so WhatsApp previews load. Pages usable on a mid-range Android phone on 4G. |
| Reliability | Scheduled messages delivered within 2 minutes of their due time, surviving restarts. Daily database backups with point-in-time recovery. |
| Time | All cutoffs computed from the stored departure time and displayed in IST with the day of the week, never as "48 hours before". |
| Accessibility | Tap targets at least 44 px, readable contrast in light and dark mode, every action reachable without gestures. |

## Risks, open questions and launch plan

The biggest risk is that people will not pay an advance to a stranger; the Diwali concierge test answers that before any code is written.

### Risks

| Risk | Mitigation |
| --- | --- |
| Passengers refuse to pay an advance to someone they don't know | Test in the concierge run. If refusals are common, lower the floor to ₹200 and lean on vouching and admin verification. |
| Drivers don't refund when the policy says they must | Open disputes shown publicly on the profile. Escrow moves into v2 if disputes exceed 5% of refunds owed. |
| Demand only exists in a few festival weeks each year | Keep the app light between peaks; reach people through WhatsApp groups rather than expecting them to open the app. |
| Matched users swap numbers and skip the app next time | Acceptable in the MVP, which has no commission. The reliability record only grows for people who book through the app, which is the reason to come back. |
| A safety incident destroys trust in the community | Women-only rides, report and block at launch; manual review of every report; clear terms. |
| Carpool rules change or are enforced differently | Fare cap and per-driver ride counts already tracked; lawyer review before public launch. |
| Group admins see the app as competition | Talk to admins before launch; ride cards are posted into their groups, not away from them. |

### Open questions

- [ ] What late cancellation rate do drivers actually experience today? Measure it in the concierge test.
- [ ] Is 30% the right advance, or does a fixed amount per seat feel fairer?
- [ ] What fuel cost per km and toll figures go into the city-pair table, and who keeps them current?
- [ ] Do the Maharashtra carpool rules require a licence for a platform that takes no money and no commission?
- [ ] Which two or three WhatsApp groups and admins join the closed beta?
- [ ] Should co-drivers get a fixed fare discount, or should drivers set it per ride?

### Launch plan

&#91;embedded content: launch roadmap · 4 phases, 3 gates\]

Dates are proposals sized for one developer working part-time. If the concierge test fails its gate, change the policy and test again at the next long weekend rather than building.
