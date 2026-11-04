# Admin dashboard decisions

## Existing stack and money model

**Context:** The dashboard specification assumes FastAPI, SQLAlchemy, Alembic, shadcn/ui, Razorpay and integer paise. The repository implements Django/DRF and Django migrations, Next.js/Tailwind, and integer rupees. Payments are direct between participants; stored records represent claims and obligations.

**Options:** Replace the stack and introduce payment processing, or implement the dashboard against existing services and represent unavailable functions explicitly.

**Decision:** Keep the existing stack and monetary model. Do not fabricate gateway payments, payouts, webhooks, verified balances or refunds. Gateway integration and conversion of money fields require a separate product, legal and engineering decision.

**Consequences:** Gateway-related PY requirements cannot be marked complete. Aggregates must be labelled as claims or obligations rather than actual funds held.

## Admin security boundary

**Context:** Existing Django staff accounts share the rider user model and do not meet the specification's separate identity, TOTP or session requirements.

**Decision:** The new dashboard requires separate admin identities, sessions, server-side permission checks and audited actions. Existing rider bearer tokens and staff status alone must not grant access. The existing Django admin remains a separate legacy surface that needs its own production hardening and access restriction.

**Consequences:** Schema, deployment secrets and staged verification are needed. Legacy Django admin is disabled by default outside DEBUG because it does not enforce the new TOTP boundary. Enabling it requires a separately secured access path and security review; never treat its staff login as dashboard authorization. No unsafe temporary admin login should be exposed as a production-ready substitute.

**Cryptography:** Reuse the already-installed `cryptography` library (previously a transitive dependency of Web Push) as a direct dependency for TOTP and authenticated encryption. A separate `ADMIN_TOTP_ENCRYPTION_KEY` is required for admin authentication; losing it requires a controlled re-enrollment process. Never derive it from the application secret.

## Restrictions and existing bookings

**Context:** The specification requires suspensions to handle a user's future rides, holds and refunds, but does not define the resulting cancellation/refund policy. The app records payment claims and cannot actually move money.

**Decision:** On suspension, cancel the driver's future rides with full refund obligations, without adding driver late-cancellation strikes for the administrator-triggered cancellations. Apply the existing passenger cancellation policy to their own bookings. Reuse the existing booking state machines and record obligations rather than claiming to send refunds.

**Consequences:** This decision authorizes the suspension policy only. Ban and automatic restriction policies, partial-failure recovery and historical records still need explicit handling before those actions are exposed.

## Logs and metrics

**Context:** The repository has basic Python logging and health endpoints but no configured external log provider, error tracker or request-latency metrics.

**Decision:** Do not invent system health numbers or link to an unconfigured vendor. Implement instrumentation using the existing stack and show unavailable data honestly; a production log/metrics provider requires an operational choice.

**Consequences:** System log search, job history and externally measured health remain incomplete until instrumentation and infrastructure are available.

## Support ticket SLA targets

**Context:** The specification requires configurable SLA targets but does not provide approved timings.

**Decision:** Leave P0, P1, P2 and P3 targets unset until the user decides them.

**Consequences:** Do not fabricate breach deadlines or breach counts. Ticketing must show an honest unset/unavailable state until targets are configured.

## Admin API schema and typed web client

**Context:** The specification requires a generated OpenAPI client and the existing project has no OpenAPI generator.

**Decision:** With the user's approval, add `drf-spectacular` for the Django admin schema and `openapi-typescript` to generate TypeScript types. Keep the schema scoped to the new admin API so existing rider endpoints retain their current behavior.

**Consequences:** The schema must be regenerated alongside admin endpoint changes and checked into the repository; generated types describe the backend API rather than adding a second, independently maintained contract.

## Enforced emergency controls

**Context:** Operators need switches that actually affect the current ride and booking services. A stale Redis entry could delay a critical pause; the specification asks for Redis caching and also timely operational control.

**Decision:** Implement new-ride posting and new-booking controls, plus a noncritical signup control. Critical enforcement reads the database directly rather than Redis, so a cached value cannot prolong a pause. The signup setting uses a 30-second cache, falling back to the database. If the database cannot be read, the declared default is returned and the operation itself still requires the database. The scheduler resumes eligible waiting lists after bookings are re-enabled. Already-running requests may finish, and existing waitlist offers may expire while paused.

**Consequences:** This intentionally differs from the blanket Redis-cache requirement; performance and concurrency must be measured on PostgreSQL. Other required flags and a robust pause policy for existing waitlist offers remain unimplemented. The UI warns about in-flight requests and expiring offers.
