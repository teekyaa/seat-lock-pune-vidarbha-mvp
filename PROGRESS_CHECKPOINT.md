# Admin dashboard progress checkpoint

Checkpoint: 2026-11-05. Current branch: `feature/prototype-improvements`. All changes are uncommitted and unpushed. Do not commit, push, or deploy without the user's approval.

## Implemented so far

- Discovery and decisions: `docs/admin/DISCOVERY.md`, `docs/DECISIONS.md`, `docs/admin/BACKLOG.md`, `docs/admin/RBAC.md`, `docs/admin/PRODUCTION_READINESS.md`, and `docs/admin/RUNBOOK.md`.
- A separate Django admin identity and session system with password, TOTP, encrypted TOTP secrets, role permissions, login limits, idle and absolute expiration, and reauthentication. A one-time interactive bootstrap command creates the initial administrator. No initial administrator or secret is assumed to have been configured.
- Admin API, generated OpenAPI schema and TypeScript types, append-only audit events with a PostgreSQL trigger, permission checks, redaction and request IDs. The `/control/audit` screen supports filtering and pagination for authorized administrators.
- `/control/login` and an early command center; server-held admin session cookies, responsive light/dark styling, refresh, and logout.
- Three enforced operational controls for new rides, bookings and signups, with change history and audit events. Critical controls require fresh reauthentication and confirmation. This is only a subset of the specified controls.
- A bounded admin settings API for P0–P3 support response targets. All targets remain **unset** until the user decides otherwise; tickets and SLA calculation are not implemented.
- Backend regression tests and isolated Playwright tests with synthetic accounts, no real SMS, plus PostgreSQL-only tests.

## User decisions

- Approved dependencies: `drf-spectacular` and `openapi-typescript`.
- On a future user suspension, cancel future rides driven by that user, record full refund obligations, and do not issue late-cancellation strikes; apply the existing passenger cancellation policy to their bookings. This suspension behavior is **not implemented**.
- Leave all P0–P3 SLA targets unset until decided.

## Validation and current risks

- Frontend ESLint and TypeScript checks passed before the last generated schema update. Regenerate and rerun them when resuming.
- The full non-stress Django suite passed against isolated local PostgreSQL before the most recent settings, audit-redaction, and browser changes. Targeted settings, audit API, audit trigger and concurrent TOTP tests passed on PostgreSQL before the last redaction-at-write adjustment; targeted SQLite settings, audit and permission tests also passed.
- An earlier isolated Playwright run passed the synthetic TOTP login, refresh, control change/revert and logout journey. A later expanded run failed because the Next.js test server was not ready; a readiness wait was added to the test harness, but the expanded audit-screen journey and wait have **not** been rerun and verified.
- Automatic approval review rejected the attempted browser-test rerun because the user requested no lengthy tests and a checkpoint. Do not work around that rejection; resume testing only when the user asks to continue.
- PostgreSQL migration `0008_platformsetting` was generated; it has been applied in disposable test databases, but must be applied to the actual local development database before using the settings API. Do not assume earlier Django development processes have loaded the latest code.
- Redis-backed distributed behavior, production proxy/HTTPS, real staging, performance, comprehensive security and full browser coverage are not verified. SQLite does not have the PostgreSQL audit trigger. Production readiness remains **NOT READY**.
- The last audit changes redact stored admin event data and flag reasons; their effect on the existing regression tests still needs verification. The audit-screen E2E and feature flag history should be reviewed for usability and authorization.
- A disposable PostgreSQL instance was started on `127.0.0.1:55432` under ignored `.admin-postgres-test/`; its data is synthetic. Check whether it is running before reuse. Do not confuse it with the application's database or use real data.

## Major unfinished work

The specification in `C:\Users\teeka\Downloads\ADMIN DASHBOARD SPEC.md` is not complete. Admin account creation/management beyond initial bootstrap, full settings and controls, complete command center and health metrics, users/rides/locks administration, tickets and workflow, risk review, alerts, exports, full observability, and full accessibility/E2E testing remain outstanding. Actual payment processing, gateway refunds, payouts and several risk signals do not exist in the current product; do not present them as real or fabricate data. See the backlog and readiness documents for detailed gaps.

## Resume instructions

1. Read this checkpoint, the complete dashboard specification, `docs/admin/DISCOVERY.md`, `docs/DECISIONS.md`, `docs/admin/BACKLOG.md`, and `docs/admin/PRODUCTION_READINESS.md`. Inspect `git status` and preserve all existing changes.
2. Review the latest changes, especially `api/apps/admin_dashboard/`, `api/tests/test_admin_settings.py`, `api/tests/test_admin_audit_api.py`, `web/src/app/control/audit/`, and `api/tests/run_admin_browser_e2e.ps1`. Verify migration `0008` and apply migrations to the intended local development database only after checking its configuration.
3. Regenerate the schema with `cd api; .\.venv\Scripts\python.exe manage.py spectacular --urlconf apps.admin_dashboard.schema_urls --file ../docs/admin/openapi.yaml --validate`, then `cd ../web; npx openapi-typescript ../docs/admin/openapi.yaml -o src/lib/admin-api.generated.ts`.
4. Run `npm run lint` and `npx tsc --noEmit` in `web/`; run Django tests in `api/` using an isolated database and no real SMS. For synthetic Windows browser tests, run `api/tests/run_admin_browser_e2e.ps1` from `api/`; it uses dedicated ports and refuses to overwrite its disposable database. Consult `docs/admin/README.md` for setup and the separate admin bootstrap process.
5. Recheck PostgreSQL trigger, permission and concurrency tests using an isolated PostgreSQL instance; document Redis/staging limitations honestly. Continue the specification in phases only after tests pass. Keep SLA targets unset and implement the agreed suspension policy before exposing suspension controls.
6. Update the phase report, backlog and readiness document as work progresses. Do not claim production readiness without completing the remaining requirements and verification.
