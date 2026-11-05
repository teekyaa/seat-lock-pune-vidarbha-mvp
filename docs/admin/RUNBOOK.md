# Admin operations runbook — incomplete

This is a development runbook. Staging verification, incident contacts, and escalation procedures are still required before public operation.

## Implemented controls

An authorized super admin can pause or resume `rides.new_ride_creation_enabled` and `bookings.new_bookings_enabled` from the command center. Each requires the exact control key, a reason, and a password plus a fresh TOTP verification within the last ten minutes. The current admin session may need a new authenticator code. The screen shows status, change history and an audited way to restore an earlier boolean value. Requests already executing may finish after a pause.

Pausing ride creation does not cancel existing rides. Pausing bookings blocks new requests, waitlist joining and accepting waitlist offers. Existing bookings remain active, and offers may expire while paused. After re-enabling bookings, the scheduler must be running to offer eligible waitlist seats again. Confirm the scheduler is healthy and review affected offers; this behavior has not been validated in staging.

An ops admin or super admin may pause `signup.new_signups_enabled`; existing users can still sign in. This noncritical setting is cached for up to 30 seconds. If Redis is unavailable, the application reads the database; when both fail, it uses the configured default, and operations needing the database remain unavailable.

## Unavailable controls and incidents

- **Payments failing / webhook backlog:** Seat Lock has no gateway, payment webhook or automated refunds. Payment records are participant claims and obligations. Contact the operational owner and use the agreed manual payment-support process; do not claim a refund was sent by the app.
- **Mass cancellations:** There is no admin mass-cancel workflow. Review each case under the existing policy and the selected suspension decision in `../DECISIONS.md`; no dashboard action currently automates it.
- **Suspected fraud ring:** There is no admin risk engine or linked-account investigation screen yet. Escalate through the existing restricted operations channel; do not infer a risk score.
- **Admin account compromise:** There is no dashboard action for admin management yet. Restrict the affected account through a controlled database/operations procedure, revoke its sessions, rotate exposed secrets as appropriate and involve the security owner. A tested recovery procedure is still required. The old Django admin does not provide the new TOTP guarantee.
- **Other requested kill switches:** Maintenance mode, read-only mode, payment/refund/payout controls, route pauses, WhatsApp, app-version settings and automatic risk restrictions are not implemented. No switch for those functions is presented as operational.

Do not use this document as proof of compliance or as a substitute for a tested incident response plan.

## Sign-in abuse flags

Django admin, **Accounts > OTP abuse flags**, lists phone numbers and IP addresses that kept hitting sign-in code limits; the dashboard overview shows how many are blocked now and flagged today. A number is blocked from requesting codes for 24 hours after five limit hits, doubling for each repeat up to 7 days. An IP is blocked for 1 hour, since mobile carriers share one address across many people. Blocks lift on their own at the time shown.

- A genuine user locked out: check the reason and history, then use **Unblock now and mark reviewed**.
- Clear abuse (many numbers from one IP, repeated wrong codes): use **Block code requests for 7 days** and add a note. To stop an existing account signing in, suspend the user instead.
- Many IP flags at once or the global hourly cap being hit (`otp_busy` in logs) can mean an SMS pumping attack: lower `OTP_GLOBAL_SENDS_PER_HOUR`, enable Cloudflare rate limiting on `/api/proxy/auth/otp/request`, and check the provider bill.

## Managing route legs before the dashboard covers them

Route legs are measured and verified in the legacy Django admin. In production set `DJANGO_LEGACY_ADMIN_ENABLED=1` together with `ADMIN_IP_ALLOWLIST` (the app will not start with one and not the other), do the leg work at `/admin/routes/`, then turn it off again.
