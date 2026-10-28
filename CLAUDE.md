# Seat Lock (working title)

Mobile-first web app for cost-sharing carpools between Pune and Vidarbha (Nagpur, Wardha, Chandrapur). It cuts last-minute cancellations by locking every seat with a UPI advance under a time-based refund policy. Built to work alongside the community WhatsApp groups, not replace them.

Full PRD: `docs/PRD.md` (exported from the Claude Doc; not in the repo yet). `PRD_REVIEW.md` records how the prototype maps to each PRD story, contradictions in the PRD, and decisions still open. If the code and the PRD disagree, the code is the source of truth for what exists; the PRD is the source of truth for what we intend. Flag mismatches instead of silently "fixing" either.

## Current status

The production stack is built (`api/` Django + DRF + Celery, `web/` Next.js). The old Node/SQLite demo lives in `prototype/` for reference only. Build plan and the decisions taken to unblock it: `docs/PRODUCTION_PLAN.md`.

- Built so far:
  - Phone OTP sign-in (hashed codes, 5 min expiry, 5 tries, per-phone and per-IP send limits), bearer tokens kept in an httpOnly cookie by the web app, profiles, saved cars, UPI ID.
  - Ride posting with fair fare suggestion and 15% cap from `city_pairs`, search, server-rendered ride pages with per-ride OG images and WhatsApp share.
  - Full booking flow with row locking, UPI deep link, cancellation tiers, refill refunds, driver cancel with season strikes, reschedule rule, waitlist offers, reconfirmation, trip confirmation, no-show and dispute, refund received and overdue disputes, report and block, women-only (staff-verified), append-only reliability events with a materialised public record.
  - Notification rows + per-minute tick (Celery beat in prod, `manage.py run_scheduler` locally) delivering in-app, email and Web Push.
  - Django admin ops console: no-show rulings, reports, reliability corrections, women-only verification, policy versions, city pairs, seasons, audit log.
  - 100 pytest tests in `api/tests` (one, the last-seat race, runs only on PostgreSQL).
- In progress: nothing.
- Known issues / not done:
  - Tests have only run on SQLite so far. Run them against PostgreSQL before relying on the row-locking guarantees.
  - SMS provider not chosen; `ConsoleSMSBackend` only. Needs a DLT-registered provider.
  - City pair distances, tolls and fuel cost are placeholders (`seed_reference_data`).
  - Photos are a URL field; no object storage. Seat-wanted, vouching, ID verification provider and emergency trip sharing are not built.

## Scope

In the MVP: phone OTP signup and profiles, ride posting with fair fare suggestion, WhatsApp share cards, ride search, seat requests and acceptance, UPI advance via deep link, cancellation tiers, reconfirmation messages, waitlist with automatic refill offers, reliability record, post-trip confirmation, women-only rides, report and block.

Not in the MVP (do not build unless asked):
- Train ticket resale or transfer of any kind
- Escrow, in-app payments, payment gateways, commissions
- In-app chat, live GPS tracking, native apps
- Other corridors, commute pooling, smart matching, dynamic pricing

## Hard rules

1. **The app never holds money.** It generates UPI deep links (`upi://pay?pa=…&pn=…&am=…&cu=INR&tn=<booking code>`) and records claims ("I've paid", "Advance received", "Refund received"). No gateway integration.
2. **Fares stay cost-sharing.** Suggested fare = (distance_km × fuel_cost_per_km + tolls) ÷ (seats offered + 1). Driver may go at most 15% above it. Distance and tolls come from the `city_pairs` table, not a maps API.
3. **Contact details are private until confirmation.** Phone numbers, UPI IDs and car registration are visible only to confirmed co-travellers on the same ride.
4. **Never store ID numbers.** ID verification stores only result, provider and date.
5. **Every booking stores its `policy_version_id`.** Policy changes never apply retroactively.
6. **Time:** store UTC, display IST with weekday. Show users exact cutoff timestamps, never "48 hours before".
7. **Money amounts are integer rupees.**
8. **Dev data stays synthetic.** Never commit databases or `.env` files. `seed_demo` and `OTP_DEBUG_ECHO` are development only.

## Cancellation and advance policy

Values live in `policy_versions` (current defaults shown).

- Advance = 30% of seat fare, rounded to nearest ₹50, min ₹300, max ₹1,000. Paid passenger to driver directly.
- Seat confirms only when the driver taps "Advance received". Unpaid holds expire after 2 hours.

Passenger cancels:
| Timing before departure | Advance |
| --- | --- |
| More than 48 h | Full refund, due within 24 h |
| 48 h to 12 h | Driver keeps half |
| Under 12 h or no-show | Driver keeps all |
| Seat refilled before departure | Full refund, any timing |

Penalty-tier outcomes are decided at departure or on refill, whichever is first (`refund_outcome = 'pending_refill'` until then).

Driver cancels: full refund to all passengers, due within 24 h. Under 48 h it is a late cancellation on their public record; a second late cancellation in one festival season blocks posting for the rest of that season. Moving departure by more than 2 h after confirmation lets passengers cancel free and counts as a driver change.

No-show: driver can mark it from departure + 30 min; passenger has 24 h to dispute. A refund unconfirmed 24 h after its due date shows as an open dispute on the driver's profile.

## Booking status flow

`requested → accepted → advance_claimed → confirmed → completed`

Exits: `declined` / `expired` (from requested), hold expiry (from accepted, after 2 h unpaid), `cancelled_passenger`, `cancelled_driver`, `no_show` (from confirmed). Only confirmed bookings count against seats or create reliability events.

## Data model (summary)

`users`, `vehicles`, `city_pairs`, `policy_versions`, `seasons`, `rides`, `bookings`, `payments` (records only), `waitlist_entries`, `trip_confirmations`, `reliability_events` (append-only; corrections are new events), `vouches`, `reports`, `blocks`, `seat_wanted`, `notifications`, `audit_log`. The public reliability record is a materialised view over `reliability_events`. Full DDL is in the PRD; the Django models in `api/apps/*/models.py` are the implemented schema.

## Stack and architecture

- Web: Next.js (App Router), TypeScript, Tailwind, PWA, on Vercel. Ride pages are server-rendered with per-ride Open Graph images so WhatsApp previews work.
- API: Django + Django REST Framework on Railway. Django admin is the ops console for disputes, reports and admin verification.
- Jobs: Celery worker + Celery beat, Redis broker.
- Data: PostgreSQL 16, Redis (OTP rate limits, cache, queue).
- SMS: Indian provider with DLT-registered OTP templates. Email + Web Push (VAPID) for everything else.

Where things live:
- `api/apps/core/policy.py`: pure fare, advance and cancellation arithmetic. `api/apps/bookings/services.py`: every booking, payment and waitlist write. `api/apps/bookings/sweeps.py`: time-driven state changes. `api/apps/notifications/`: rows, schedule, dispatcher. `api/apps/bookings/presenters.py`: JSON shapes and contact gating.
- `web/src/app/api/proxy` forwards browser calls to Django with the cookie token. `web/src/app/session` signs in and out. Server components call `api()` from `web/src/lib/server.ts`.
- Commands: `uv run pytest`, `uv run python manage.py run_scheduler`, `seed_reference_data`, `seed_demo` (DEBUG only). Web: `npm run dev`, `npm run build`, `npm run lint`.

Implementation decisions to keep:
- **Scheduled messages are rows, not delayed tasks.** Every reminder lives in `notifications`. A beat task runs every minute, claims due rows with `SELECT … FOR UPDATE SKIP LOCKED`, sends, marks sent. No one-off ETA tasks.
- **Seat counts use row locking.** Confirming an advance or accepting a waitlist offer locks the ride row, counts confirmed bookings, and confirms only if a seat is free, in one transaction.
- **Holds reserve seats.** `accepted`, `advance_claimed` and open waitlist offers count against capacity so two people never pay for one seat. Only `confirmed` bookings create reliability events. (Deliberate deviation, see `docs/PRODUCTION_PLAN.md`.)
- **Never raise inside a transaction after saving a state you want kept** (an expiry, a failed OTP attempt). Commit first, then raise. Tests cover both cases.
- Modular monolith. No microservices.

## Notification schedule (relative to departure)

| When | Who | Action | If ignored |
| --- | --- | --- | --- |
| On confirmation | Both | Shows exact cutoffs | n/a |
| 72 h | Passenger | "Still coming?" | Repeated at 48 h |
| 48 h | Both | Reconfirm | After 6 h: seat flagged at risk, waitlist alerted |
| 12 h | Both | Reconfirm + pickup details | Driver can call |
| Departure + 30 min | Driver | Mark no-show | None |
| Expected arrival | Both | "Did this trip happen?" | Reminder after 24 h |
| Refund due + 24 h | Passenger | "Refund received?" | Open dispute on driver profile |

## Conventions

- UI copy: plain, conversational, no em dashes.
- Write tests for every policy rule and status transition before changing them (`api/tests`, pytest with a frozen `clock` fixture).
- Ask before adding a dependency or a third-party service.
- Keep `README.md` and `PRD_REVIEW.md` in sync when a story's state changes.

## Open questions

- Real baseline late-cancellation rate (from the Diwali concierge test)
- Is 30% the right advance, or a fixed amount per seat?
- Source and upkeep of fuel cost and toll figures
- Whether Maharashtra carpool rules require a licence for a platform that takes no money
- Co-driver fare discount: fixed or per ride?
- Which Indian SMS provider (DLT-registered OTP templates)
- Sign-off on the decisions listed in `docs/PRODUCTION_PLAN.md`
