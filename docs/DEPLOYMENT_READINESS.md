# Deployment readiness — 2 November 2026

**Verdict: NOT READY.** A 500-user capacity, PostgreSQL concurrency correctness, public deployment security, and Maharashtra carpool compliance have not been established. This is an engineering assessment of the inspected code and locally executed checks, not an independent security certification.

## Environment and initial condition

The audit used a Windows 11 development machine with 12 logical CPUs and 15.8 GiB RAM. Its active Django database is SQLite and its cache is process-local. No isolated PostgreSQL, Redis or production-sized load generator was available for the tests below. The repository already had uncommitted fare-policy changes; they were preserved. The app uses Next.js, Django/DRF, a bearer token held by an httpOnly frontend cookie, PostgreSQL/Redis support, and an Android TextBee gateway. Payment and refund records reflect participant claims; no payment gateway or escrow verifies or moves money.

## Findings and changes

| Severity | Status | Finding and response |
| --- | --- | --- |
| Critical | Mitigated in code; deployment unverified | Next.js 15.5.4 and React 19.1.0 matched a critical React flight protocol advisory. Updated Next.js to 15.5.28, React to 19.1.2 and patched vulnerable transitive PostCSS/sharp versions. Verify compatibility and the current advisory database before deployment. |
| High | Mitigated; staging verification required | Production now refuses SQLite, an absent Redis URL, and short/example Django secret keys. HTTPS proxy headers are trusted only with explicit configuration. Cache availability, proxy header sanitization and database connection limits must still be tested in the intended infrastructure. |
| High | Mitigated; wider testing needed | Push subscription destinations now use an HTTPS provider allowlist, deny redirects, and use a timeout. Existing subscriptions are checked at send time. The chosen provider hosts require review if browser vendors change endpoints. Network-level egress controls are still recommended. |
| High | Partially mitigated, PostgreSQL verification missing | Booking services use transactions, locks and unique constraints. An expired unpaid hold can no longer be confirmed; locks on joined rows were narrowed. Last-seat and 100-way race tests require PostgreSQL and have not run here. Other races and recovery cases remain untested. |
| High | Partially mitigated | Failed external notification channels are recorded and retried up to three times without resending channels already recorded successful. The in-app notification remains visible. Sends still occur inside a transaction; a process crash after provider acceptance, or a partial failure across a user's push subscriptions, can cause duplicates on retry. Monitor `last_error` and `next_retry_at`; end-to-end delivery and provider idempotency remain unverified. |
| High | Open | No measured 500-user workload or 30-minute sustained run exists. Current workers, connection limits, indexing, query latency and infrastructure capacity are not sized from evidence. |
| Medium | Mitigated in code, staging verification needed | OTP verification has an IP limit in addition to send limits and per-challenge attempts. Locally the live TextBee flow was previously checked with one user, including refresh and logout. The deployed proxy must supply a trustworthy client IP; no throughput or outage capacity is established. |
| Medium | Mitigated in code | Browser proxy/session writes check Origin, request bodies have limits, unsafe redirect destinations are rejected, and booking API boolean/fractional-number handling is stricter. Verify Origin behavior through the real HTTPS proxy and perform broader adversarial testing. |
| Medium | Partially mitigated | Ride-list availability reuses annotated counts. Public profile/reliability presentation and booking lists may still issue repeated queries; measure query counts and plans with realistic PostgreSQL data before tuning indexes. |
| Medium | Open | TextBee's Android phone, SIM, carrier, network and provider availability limit throughput and reliability. A provider interface exists, but acceptance of a request is not proof of delivery. An outage must never activate development OTP echo. Production-grade SMS, operational alerts and telecom requirements need review. |
| Medium | Open | Route distances, tolls and operating cost are placeholders. The local fare policy applies estimated conservative limits but the legal cost definition and rules have not been validated for this product. Obtain Maharashtra legal advice on carpooling, licence/registration, insurance, fares and aggregate contributions before public use. |
| Medium | Open | Authentication, ownership, input validation, CSRF, SSRF, error handling and data privacy have not received a complete independent penetration test. Particularly test proxy trust, concurrent OTP attempts, untrusted inputs and object-level access. |
| Low | Open | Some older documents still describe the previous fare policy; deployment and operating procedures need owner review. |

## Verification performed

- Django pytest suite on SQLite: passed, with **two PostgreSQL-only concurrency tests skipped**. No real SMS is sent by the test fixtures. The latest run covers OTP, fare limits, booking paths, access checks, notification retry and several security regressions; it does not establish absence of races.
- Next.js production build and lint: passed locally. Build requires network access to fetch the configured Google font. Four Playwright checks run against a local production build using mocked SMS/session responses: login error handling, mobile layout, cross-origin write rejection, and malformed/oversized requests. These are limited browser checks, not full ride lifecycle end-to-end coverage.
- `npm audit --omit=dev` after updates: zero reported vulnerabilities at the time of the check. The full install reported moderate development dependency advisories. `pip-audit` on the locally installed Python environment reported no known vulnerabilities after updating local pip; this is not a separate audit of every possible production lockfile resolution.
- GitHub Actions workflow added for PostgreSQL/Redis API tests, frontend build/lint and mocked browser checks. It has not run on GitHub. The 100-thread stress test is excluded from normal CI and requires a separately sized PostgreSQL instance.
- `/healthz` is a liveness check; `/readyz` checks database and cache, returning only a boolean. No infrastructure monitoring has been deployed.

## Load testing and resource needs

**No RPS, latency, error-rate, CPU, memory, database-connection, query-time or maximum-user results were measured.** Consequently there is no evidence that the 500-user, 30-minute target is met. See `api/loadtest/README.md` for synthetic data setup, guarded Locust workloads, 50/100/250/500-user stages and metrics. Execute on isolated PostgreSQL/Redis infrastructure with a separate load generator; check generator saturation and inventory integrity.

Until measured, choose infrastructure by staged testing rather than a promise of a particular instance size. A reasonable **starting experiment**, not a production sizing recommendation, is two application instances with 2 vCPUs and 4 GiB RAM each, a separate managed PostgreSQL instance with at least 2 vCPUs and 4 GiB RAM, a separate Redis instance, and a separate load generator. Adjust workers and PostgreSQL connection limits based on observed utilization and per-request connection use. Calculate maximum connections across all web workers, Celery workers, migrations and administrative access. Provisioning and cost require owner approval.

## Deployment preparation

1. Obtain approval for the hosting architecture, budget, legal position and SMS provider. Use supported patched dependency versions and rerun package audits and the full test suite.
2. Provision isolated staging first. Use PostgreSQL and Redis with authentication, encryption and network restrictions; do not use SQLite for public service. Store credentials in the hosting secret manager and restrict access. Configure `DJANGO_DEBUG=0`, a unique strong `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, allowed hosts, site/API URLs, SMS credentials and email/push settings. Never enable debug OTP echo in production.
3. Terminate HTTPS at a trusted proxy. Set `DJANGO_TRUST_PROXY_HEADERS=1` only if that proxy strips and sets forwarding headers, and restrict direct access to Django. Configure CSRF trusted origins and a verified client-IP chain for OTP throttling. The Next.js proxy only forwards a client IP when `SEATLOCK_CLIENT_IP_HEADER` names a header overwritten by trusted ingress; Django must also trust only its actual proxy addresses via `OTP_TRUSTED_PROXY_IPS`. Without this configuration, users behind the proxy share an IP rate limit. Verify the header chain, frontend Origin checks, cookie security and login through the actual domain. Protect admin access and configure edge request limits.
4. Run migrations as a controlled release step before starting compatible application workers. Start Django with a production WSGI server, Next.js production build, Celery worker and exactly one scheduler. Configure timeouts, readiness/liveness checks, structured logging, alerting, centralized error monitoring and sensitive-data redaction. `/readyz` needs both the database and cache.
5. Exercise login with a non-production SMS backend, ride/booking workflows, notifications, restart and failure recovery in staging. Run the PostgreSQL concurrency suite, browser tests and guarded load stages. Record capacity and resource consumption before allocating production resources.
6. Before a release, take a verified encrypted PostgreSQL backup and test a restore on a separate instance. Retain and rotate backups according to an approved recovery objective; test Redis recovery and document whether it is only a cache/broker. Secure any object storage if added. No backup or restore has been tested in this audit.

## Rollback

Keep the previous application images, dependency lockfiles and deployment configuration available. Stop or drain new traffic, deploy the prior compatible application release and monitor health and queue processing. Review each migration for backward compatibility before release: database rollback may require a tested forward fix or a separately approved restore, with an explicit data-loss window. Never assume that reverting application code reverses a migration. Restore backups only under an approved incident procedure after rehearsing on a separate database.

## Outstanding release gates

- Execute the PostgreSQL race tests, failure-injection tests and 500-user sustained workload; confirm no oversold seats or data corruption.
- Complete end-to-end coverage for ride creation, booking, cancellations, waitlists, sessions and accessibility on mobile browsers.
- Review remaining security findings and transitive advisories, proxy trust, logging, secret rotation, SMS abuse and admin exposure.
- Validate backup/restore, worker recovery, monitoring, staged rollback and current legal/operational obligations.
