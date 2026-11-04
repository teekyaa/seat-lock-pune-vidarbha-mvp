# Admin dashboard production readiness

**Status: NOT READY.** The separate admin authentication and overview are a foundation under development. They do not satisfy the complete dashboard specification.

- [ ] Migrations up and down verified on PostgreSQL; audit trigger verified with a separate runtime role. SQLite does not enforce the PostgreSQL audit trigger.
- [x] Required admin encryption configuration documented; no real secrets are included in the repository.
- [x] Initial administrator creation is an interactive, one-time CLI command; there is no public bootstrap endpoint.
- [ ] Admin TOTP, separate sessions, idle and absolute expiration, logout, and browser same-origin checks have automated local coverage; end-to-end behavior, TOTP replay under concurrent PostgreSQL requests, re-authentication and CSRF through the actual production proxy still require verification.
- [ ] Login rate limiting exists using the configured cache; Redis availability, proxy IP trust and distributed limits remain to be verified in staging.
- [ ] Admin management, settings service, most specified kill switches, support tickets and risk review are not implemented. Two critical switches (new rides and new bookings) and a cached noncritical signup switch are implemented; critical changes require recent password/TOTP re-authentication and an audit record. Their PostgreSQL concurrency and staging behavior remain unverified.
- [ ] No payment gateway, real refunds, payouts, payment webhooks or reconciliation exist in Seat Lock. Do not present payment claims as confirmed payment processing.
- [ ] Admin audit events have a redacting JSON log formatter and request IDs, but consistent structured/redacted logging across the whole app, an external log/metrics provider, error tracker, admin job history and staging alert checks are not implemented.
- [ ] Main list queries have not been benchmarked against 100,000 rows; PostgreSQL query plans and 500-user load targets remain unverified.
- [ ] Backup/restore, migration rollback, worker recovery, separate app and migration DB roles, and audit-table privileges have not been rehearsed. The existing product readiness report is `docs/DEPLOYMENT_READINESS.md`.
- [ ] CI exists for the application; generated admin schema/client drift, admin browser journeys, admin coverage and PostgreSQL audit-trigger checks must be added or verified.

The existing legacy Django admin is disabled by default outside DEBUG because it does not enforce the separate TOTP boundary. Enabling it requires an independently protected access path and security review.
