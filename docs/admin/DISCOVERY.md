# Admin dashboard discovery

## Existing application

- The current branch is `feature/prototype-improvements`. Django 5.2, Django REST Framework and Django migrations provide the API; Next.js 15 App Router, TypeScript and Tailwind provide the web app. The existing web app does not use shadcn/ui or TanStack Query.
- The API supports PostgreSQL and Redis for production, SQLite and a process-local cache for local development, Celery for scheduled work, and Django admin at `/admin/`. The existing staff account is a rider/driver `User`, not a separate admin identity. Its bearer-token API authentication is intended for riders, not admin sessions.
- `Ride` represents a published trip. `Booking` contains the current seat request, hold and confirmation state machine; accepted and advance-claimed bookings hold seats. Booking services enforce business rules using transactions and row locks on PostgreSQL. The existing Django admin makes bookings read-only, but some other admin actions update rows directly.
- `Payment` represents participant claims and refund obligations in integer rupees. Seat Lock has no Razorpay gateway, payment webhooks, payouts, reconciliation service or verified funds held. A dashboard must never report those as real gateway transactions or initiate gateway refunds.
- The existing `Report` is a basic reporter/reported-user incident with open/actioned/dismissed statuses. It is not a support ticketing system: assignments, SLA, thread, internal notes and escalation are absent. There is no risk rules/flags engine, device fingerprint, ratings, chat or linked-account graph.
- Existing `AuditLog` is general application activity, lacks the requested admin context and before/after values, and is not database-enforced append-only. The existing Django admin authentication does not meet the separate admin identity, mandatory TOTP and session requirements.
- Existing test tooling is pytest/pytest-django and Playwright; the PostgreSQL concurrency tests have not been verified locally. CI configuration exists. See `docs/DEPLOYMENT_READINESS.md` for outstanding production and legal gates.

## Gaps and planned schema

1. Separate admin accounts, permission mapping, TOTP enrollment and verification, revocable admin sessions, Redis-backed limits, and secure bootstrap command are absent. A production-grade implementation needs explicit encryption-key management, recovery and session-revocation design before exposure.
2. A separate admin audit ledger needs transactional writes, redaction, and PostgreSQL-level protection against update/delete. The application DB role and migration role must be separated for production; SQLite tests alone cannot prove this.
3. Support tickets need their own model, assignment, immutable history and message visibility rules, with an explicit mapping from existing reports. Safety reports must not silently become resolved or lose evidence.
4. Risk rules and restriction actions require new persisted models, defined signals and transactional lifecycle handling. Absent signals (chat, ratings, devices) must be shown as unavailable rather than fabricated. Restriction effects on existing rides, bookings and refunds need an explicit approved policy.
5. Feature flags, settings, alerts, health metrics, job-run history and exports do not exist. New controls must be enforced by backend services and must fail safely; do not expose switches whose effects are not implemented.
6. Payments, webhook, payout and reconciliation modules are blocked by the absence of a gateway. Support the existing claim/refund-obligation records honestly; record provider-dependent functionality as a gap.
7. The current UI has no admin shell, generated API schema/client, dark theme or component test stack. The admin surface needs its own authentication and route isolation, without exposing rider session tokens or data to unprivileged users.
8. The existing API error envelope uses `detail` and `code`; any admin-specific envelope and OpenAPI generation must be introduced without breaking rider endpoints.

## Phase 0 report

- Requirement IDs: discovery for AD-1–AD-7, AU-1–AU-5, RL-1–RL-6, PY-1–PY-6, TK-1–TK-7, TS-1–TS-6, OC-1–OC-7, CC-1–CC-5, SL-1–SL-2 and EX-1–EX-3.
- Decisions and blocked product assumptions: `docs/DECISIONS.md`; out-of-scope and implementation gaps: `docs/admin/BACKLOG.md`.
- Verification: repository and specification inspected; this documentation phase changes no executable behavior. PostgreSQL/Redis integrations, coverage and production claims have not been tested in this phase.
