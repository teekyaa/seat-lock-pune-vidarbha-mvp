# Seat Lock · Pune to Vidarbha carpools

Mobile-first web app for cost-sharing carpools between Pune and Nagpur, Wardha and Chandrapur. Every seat is locked with a small UPI advance paid straight to the driver, under a time-based refund policy. The app never holds money.

| Folder | What it is |
| --- | --- |
| `api/` | Django 5.2 + Django REST Framework API, Celery jobs, Django admin as the ops console |
| `web/` | Next.js 15 App Router (TypeScript, Tailwind v4, PWA) |
| `prototype/` | The original local Node/SQLite demo, kept for reference |
| `docs/` | `PRODUCTION_PLAN.md` (build plan and decisions taken), PRD to be added |

`CLAUDE.md` holds the product rules. `PRD_REVIEW.md` tracks open product decisions.

## Run it locally

Needs Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+, and (recommended) PostgreSQL 16+. Redis is optional locally.

### API

```bash
cd api
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

Without `DATABASE_URL` the API uses SQLite. That is fine for clicking around, but row locking is a no-op there, so use PostgreSQL for anything concurrency related:

```bash
psql -U postgres -c "CREATE ROLE seatlock LOGIN PASSWORD 'seatlock' CREATEDB" -c "CREATE DATABASE seatlock OWNER seatlock"
```

Then set `DATABASE_URL=postgres://seatlock:seatlock@127.0.0.1:5432/seatlock` in `api/.env` and migrate again.

Scheduled work (expiries, reminders, refund disputes, the public reliability record) runs in a per-minute tick. Without Redis, run it in a second terminal:

```bash
cd api
uv run python manage.py run_scheduler
```

Ops console: create a staff login with `uv run python manage.py createsuperuser`, then open http://127.0.0.1:8000/admin/.

### Web

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Sign in with a seeded test number (`9000010001` driver Aditi, `9000010002` passenger Rahul, `9000010003` passenger Neha). For real SMS, set `TEXTBEE_API_KEY` and `TEXTBEE_DEVICE_ID` in the Git-ignored `api/.env`; Django selects the TextBee backend automatically. With TextBee configured, OTPs are never echoed in API responses or console logs. Without TextBee, local development uses the console backend; `OTP_DEBUG_ECHO=1` can show its code on the sign-in screen. Use Redis for shared OTP limits when running multiple API processes.

### Tests

```bash
cd api
uv run pytest
```

Every policy rule and status transition has a test. `tests/test_concurrency.py` (last-seat race) runs only against PostgreSQL.

## How it fits together

- The browser only talks to Next.js. `web/src/app/api/proxy` forwards calls to Django with the session token from an httpOnly cookie, so page JavaScript never sees the token.
- Ride pages (`/r/<code>`) are server-rendered with a per-ride Open Graph image for WhatsApp previews.
- All booking writes go through `api/apps/bookings/services.py`. Anything that changes seat counts locks the ride row first.
- Scheduled messages are rows in `notifications`. The tick claims due rows with `SELECT … FOR UPDATE SKIP LOCKED`, sends them (in-app, email, Web Push) and marks them sent.
- `reliability_events` is append-only. The public record is a materialised view over it, refreshed every tick.

## Emergency trip sharing (PRD US-26)

On a confirmed passenger booking, create a private trip link and share it through the device share sheet or copy it to a trusted contact. The read-only page shows the driver, car registration, route, pickup/drop-off and departure/expected-arrival times. It expires 24 hours after expected arrival. Creating a replacement link revokes the previous one; the passenger can also turn the link off. The API stores only a SHA-256 hash of the random link token. This is a trip-details link, not live location tracking or an emergency-response service. Localhost links cannot be opened from another device; use a deployed public URL before sharing outside the demo.

## Vouching (PRD US-24)

Signed-in members can vouch for other members and withdraw a vouch later. The prototype interprets the PRD's five-active-vouches limit as five active vouches given by each member. Public profiles show who vouched for the member and who the member has vouched for. A vouchee's unreversed late cancellations after the vouch date appear on the voucher's profile. Vouching does not verify identity, require a previous ride together, or guarantee safety.

## Seat-wanted alerts (PRD US-23)

Passengers can post an active route/date request for up to seven seats, with an exact date or a flexibility window of up to three days on either side. When a matching open ride is posted, a request is posted for an existing ride, or seats become available again, the passenger gets an inbox notification. The dispatcher also sends email or Web Push when a configured address or subscription is available. Requests can be closed; closed requests no longer receive alerts. The PRD does not set a maximum flexibility window, so this prototype caps it at ±3 days.

## Co-driver bookings (PRD US-04, US-08, US-17, US-21)

Drivers can mark a ride as looking for a co-driver. A requester can book as a passenger or choose the co-driver role; that role stays visible on the booking and driver list and is retained if they join the waitlist. Co-drivers self-attest that they hold a valid driving licence and agree to share driving. The app does not verify the licence or qualifications. In this prototype co-drivers pay the same listed fare and follow the same cancellation policy as passengers; late co-driver cancellations have a separate reliability label.

The PRD does not decide licence evidence, driving-duty and insurance terms, whether a co-driver gets a fare discount, or whether a co-driver seat is included in the cost-sharing denominator. The current fare and seat behavior is only a local prototype choice. Resolve these and obtain legal/product review before public use.

## Deploy

- **API on Railway**: `api/Procfile` defines `release` (migrate + reference data), `web` (gunicorn), `worker` and `beat` (Celery). Add PostgreSQL and Redis, and set the variables from `api/.env.example` with `DJANGO_DEBUG=0`.
- **Web on Vercel**: root directory `web`, set `API_URL` and `NEXT_PUBLIC_SITE_URL`.

## Not ready for real users yet

- **SMS rollout needs validation.** TextBee is integrated as the OTP gateway. Confirm real handset delivery, sender/telecom requirements, and operational monitoring before public use.
- **Corridor figures are placeholders.** Distances, tolls and fuel cost per km in `seed_reference_data` must be replaced with approved values.
- **Profile photos** are a URL field only. Object storage is not set up.
- **ID verification provider** is not built.
- The open decisions in `PRD_REVIEW.md` and `docs/PRODUCTION_PLAN.md` still need sign-off before a public beta.
