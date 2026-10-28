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

Open http://localhost:3000. Sign in with a seeded test number (`9000010001` driver Aditi, `9000010002` passenger Rahul, `9000010003` passenger Neha). With `OTP_DEBUG_ECHO=1` in `api/.env`, the code appears on the sign-in screen and in the API console. No SMS is sent.

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

## Deploy

- **API on Railway**: `api/Procfile` defines `release` (migrate + reference data), `web` (gunicorn), `worker` and `beat` (Celery). Add PostgreSQL and Redis, and set the variables from `api/.env.example` with `DJANGO_DEBUG=0`.
- **Web on Vercel**: root directory `web`, set `API_URL` and `NEXT_PUBLIC_SITE_URL`.

## Not ready for real users yet

- **SMS provider not chosen.** OTPs go through a pluggable backend. Production needs a DLT-registered Indian provider wired into `SMS_BACKEND`.
- **Corridor figures are placeholders.** Distances, tolls and fuel cost per km in `seed_reference_data` must be replaced with approved values.
- **Profile photos** are a URL field only. Object storage is not set up.
- **Seat-wanted alerts, vouching, ID verification provider, emergency trip sharing** are not built (models exist for the first two).
- The open decisions in `PRD_REVIEW.md` and `docs/PRODUCTION_PLAN.md` still need sign-off before a public beta.
