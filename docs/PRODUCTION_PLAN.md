# Production stack migration plan

**Status (2026-10-29):** phases 1 to 12 built locally. Emergency trip links need a public deployment to work across devices. Tests have run on SQLite only; run `uv run pytest` against PostgreSQL before relying on row-locking guarantees. Co-driver licence and fare decisions remain open for public use. See the README for current limitations.

Goal: replace the local Node/SQLite prototype with the PRD stack (Next.js web, Django + DRF API, Celery jobs, PostgreSQL 16, Redis) while keeping every rule in `CLAUDE.md`.

## Repo layout

```text
api/         Django project (seatlock) + apps, Celery, tests
web/         Next.js App Router (TypeScript, Tailwind, PWA)
prototype/   The original Node demo, kept for reference until parity is signed off
docs/        PRD (to add), this plan, decisions
```

## Phases

| # | Phase | Output | Done when |
| --- | --- | --- | --- |
| 1 | Scaffold | `api/` (uv + Django 5.2 LTS), `web/` (Next.js 15), env examples, prototype moved | Both apps boot locally |
| 2 | Data model | Models + migrations for every table in the CLAUDE.md data model; reliability materialised view | `migrate` runs on PostgreSQL |
| 3 | Domain services | Fare calculator, advance calculator, booking state machine, cancellation tiers, refill, driver cancel + season strikes, waitlist, no-show, trip confirmation | Services own every write; views only call services |
| 4 | Tests first for policy | Unit tests for every policy rule and status transition, plus concurrent last-seat test | `pytest` green |
| 5 | API | DRF endpoints, phone OTP auth with rate limits, contact-gating serializers, Django admin as ops console | API test suite green |
| 6 | Jobs | `notifications` rows + per-minute dispatcher with `SKIP LOCKED`, state sweeps (expiry, refill outcomes, overdue refunds, no-show finalise, view refresh), email + Web Push + pluggable SMS | Beat tick tested |
| 7 | Web | Login, onboarding, search, post ride with fare suggestion, ride page (SSR + OG image), booking flow with UPI deep link and exact IST cutoffs, inbox, profile, PWA manifest + service worker | Manual walkthrough of the README demo script passes |
| 8 | Deploy config + docs | Railway Procfile (web, worker, beat, release), Vercel notes, README + CLAUDE.md + PRD_REVIEW updated | Docs match code |
| 9 | Emergency trip share | Passenger-only, expiring and revocable private trip-detail links for a trusted contact | Public page reveals only the PRD fields and stops after expiry, revocation, or booking cancellation |
| 10 | Member vouching | Five-active-vouches-given limit, withdraw/reactivate, public received/given lists, late-cancellation attribution | Vouches can be created and withdrawn; accountability is displayed and explicitly disclaimed as social context |
| 11 | Seat-wanted alerts | Create/close route and date requests, match on ride/request posting and released capacity, schedule deduplicated alerts through notification rows | Requests match available seats within the selected date window; closed requests are skipped at delivery |
| 12 | Co-driver flow | Driver co-driver preference, passenger/co-driver request and waitlist roles, self-attestation, booking display, separate late-cancellation record | Role persists through direct requests and waitlist offers; one active co-driver offer/booking per ride |

## Decisions taken to unblock the build (flag for review)

These resolve P0 items from `PRD_REVIEW.md` with the safest default. Each lives in one function so it is cheap to change.

1. **Holds reserve a seat.** `accepted` and `advance_claimed` bookings count against capacity, so two people cannot pay for one last seat. Only `confirmed` bookings create reliability events. (CLAUDE.md says only confirmed bookings count against seats; this deviates on purpose.)
2. **UPI deep link before confirmation.** A passenger with an active hold sees the driver's UPI deep link, since paying requires it. Phone number and car registration stay hidden until confirmation.
3. **Cutoff boundaries.** More than 48 h before departure: full refund. 48 h down to 12 h inclusive: driver keeps half. Under 12 h: driver keeps all.
4. **Refill.** A cancelled seat counts as refilled when a later confirmation brings the ride's confirmed count back to what it was at the moment of that cancellation. Oldest pending cancellation is refilled first.
5. **Women-only eligibility** is a staff-set flag after verification, not self-declared gender. Unverified users cannot post or request women-only rides.
6. **SMS provider not chosen.** SMS goes through a pluggable backend; dev uses a console backend. A real DLT-registered provider is a third-party service and needs your choice.
7. **No Docker/Redis locally.** Celery uses Redis in production. Locally, `manage.py run_scheduler` runs the same per-minute tick without Redis, and cache falls back to local memory.
8. **Co-driver prototype behavior.** A co-driver consumes an offered seat, pays the same listed fare, follows the passenger cancellation policy, and self-attests to a valid licence and willingness to share driving. These defaults make the demo journey coherent; the PRD does not settle public-use licensing evidence, duties, insurance, discount, or seat/fare denominator.

## Out of scope for this migration

ID verification provider, group-admin pages, Hindi/Marathi. Emergency trip sharing, vouching, seat-wanted alerts, and the co-driver flow moved out of scope and are now in phases 9 to 12.
