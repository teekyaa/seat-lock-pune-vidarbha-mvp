# Admin backlog

## Explicitly outside this MVP

- Map-based live tracking, ML-based fraud scoring, four-eyes approval, custom report builder, multilingual admin UI and granular per-field permissions.

## Existing product gaps

- Payment gateway transactions, webhook processing, payouts, reconciliation and actual automated refunds: the product does not currently move or verify money.
- Driver licence and vehicle registration verification, external identity provider and verification rejection delivery: no verification integration exists.
- Risk signals requiring chat, ratings or device fingerprinting: no source data exists. Do not fabricate flags or linked accounts.
- The user selected the suspension policy: cancel future driver rides with full refund obligations and no administrator-triggered late-cancellation strikes, and apply the existing passenger cancellation policy. Implement and verify this with resumable recovery before enabling suspensions. Ban and automatic-restriction policy remains undecided.
- Centralized log provider, metrics backend and error tracker are not configured.
- The user chose to leave P0–P3 support SLA targets unset. Do not calculate breach deadlines or breach counts until targets are approved and configured.
- PostgreSQL/Redis integration, 100k-row performance checks, staging and production recovery tests remain required; the local development database is SQLite.
