# Free-tier production deployment plan (proposal, 6 November 2026)

**Status: proposal, nothing provisioned.** Picks come from the [free-for-dev](https://github.com/ripienaar/free-for-dev) list, checked against each provider's limits as of November 2026. Free tiers change without notice (Oracle halved its Arm allowance in mid-2026), so re-check each one before signing up. Each new service needs owner sign-off (CLAUDE.md: ask before adding a third-party service). This plan does not replace the release gates in `DEPLOYMENT_READINESS.md`.

## What the app needs from hosting

| Need | Why it rules out most free tiers |
| --- | --- |
| Always-on API | Hold expiry (2 h), cutoffs, reconfirmations and no-show windows are time-driven. A host that sleeps after 15 to 60 minutes delays them and adds a cold start to the first OTP of the day. |
| One scheduler process, every minute | `run_tick()` drives sweeps, notifications and the reliability view. Celery runs only this one task, so `manage.py run_scheduler` can replace both the Celery worker and beat. That removes two processes and the Redis broker. |
| PostgreSQL with row locking | Seat counts depend on `SELECT … FOR UPDATE`. A per-minute tick keeps a serverless database awake around the clock. |
| Redis (or a shared cache) | Only for OTP and admin rate limits and flag caching once Celery is gone. Production refuses to start without `REDIS_URL` today. |
| Server-rendered Next.js | Ride pages and OG images for WhatsApp previews. |
| India latency | Users are in Pune and Vidarbha. Mumbai or Hyderabad regions are best. |

### Free tiers that do not fit, and why

- **Render free:** sleeps after 15 minutes idle with about a minute to wake. Free Postgres is deleted 30 days after creation and has no backups.
- **Koyeb free:** scales to zero after 1 hour, and this cannot be turned off. Frankfurt or Washington only.
- **Neon free:** 100 CU-hours a month. A database kept awake by the per-minute tick at the smallest size (0.25 CU) uses about 180 CU-hours, so it runs out mid-month.
- **Vercel Hobby:** limited to non-commercial personal use. Seat Lock charges no commission, but anyone gaining financially counts as commercial, so this is a grey area. Avoid building on it.
- **Supabase free:** usable (Mumbai region, always on while the tick runs), but 500 MB and no backups. It's only the database in Option B.
- **Upstash free:** 500K commands a month. Enough for rate limits only after Celery is removed. A Celery broker polling it would burn through that.

## Option A (recommended): ₹0 a month, one Oracle Always Free VM

```text
Users ── Cloudflare (DNS, TLS, CDN, WAF, 1 rate-limit rule) ── Oracle Arm VM (Mumbai or Hyderabad)
                                                                 Caddy (HTTPS, reverse proxy)
                                                                 ├─ web: Next.js standalone
                                                                 ├─ api: gunicorn (Django)
                                                                 ├─ scheduler: manage.py run_scheduler (exactly one)
                                                                 ├─ PostgreSQL 16 (private network only)
                                                                 └─ Redis/Valkey (private network only)
Nightly pg_dump (encrypted) ── Cloudflare R2 or Backblaze B2 (10 GB free)
```

| Piece | Service | Free allowance (from free-for-dev, verify) |
| --- | --- | --- |
| Compute + DB + cache | Oracle Cloud Always Free, Ampere A1 | 2 Arm cores, 12 GB RAM, 200 GB block storage, 10 TB egress |
| DNS, TLS, CDN, WAF | Cloudflare Free | Unlimited DNS, DDoS protection, 1 rate-limit rule |
| Backups | Cloudflare R2 (or Backblaze B2) | 10 GB |
| Email | Brevo (SMTP) | 300 a day, 9,000 a month |
| Web Push | Self-hosted VAPID (already built) | Free |
| OTP | WhatsApp Cloud API authentication template (primary), Message Central VerifyNow SMS (fallback). TextBee stays for development. | About ₹0.115 + GST per delivered WhatsApp OTP, no DLT needed. SMS fallback is about ₹0.12 to ₹0.30 per delivered OTP, no DLT to start. Own DLT registration (about ₹5,900 a year) is needed only for a branded sender ID. Built and tested against mocked APIs; needs real accounts. |
| Pickup search | Mappls (already integrated) | Free tier, key stays server-side |
| Errors | Sentry (or GlitchTip) | 5,000 errors a month |
| Uptime | UptimeRobot | 50 monitors, 5-minute checks |
| Scheduler heartbeat | healthchecks.io | 20 checks |
| CI + backup cron | GitHub Actions | Already used |
| Domain | Any registrar, `.in` | **Paid, about ₹600 to ₹900 a year.** The only real cost. A free subdomain looks untrustworthy in WhatsApp groups. |

Why this one: everything runs in an India region on 12 GB RAM, far more than a 500-user launch needs. There's no sleep, no expiry and no metered database. Running every piece on one VM also removes the network hops between web, API and database.

Risks and how to handle them:

- **Idle reclamation.** Oracle reclaims Always Free VMs on free accounts that look idle, and a small app looks idle. Upgrade the account to Pay As You Go (needs a card). You aren't charged while you stay inside Always Free limits, and PAYG instances aren't reclaimed. Set a ₹0 budget alert.
- **Signup capacity.** Arm capacity is often "out of host capacity" in popular regions, and the home region can't be changed after signup. Pick Mumbai or Hyderabad at signup and retry the VM create. If it still fails after a few days, use Option B.
- **Single machine.** One VM is one point of failure. Mitigate with nightly encrypted off-site backups, a tested restore, the uptime monitor and the heartbeat. Accept short outages at this stage.
- **You run the server.** OS updates, Docker updates and disk monitoring are on you. Use unattended-upgrades, Postgres and Redis bound to the private Docker network only, SSH keys only, and only ports 80 and 443 open (Cloudflare IPs only).
- **Over-provisioning.** Running more Arm cores than the free allowance can get every A1 instance deleted after 30 days. Stay within 2 cores and 12 GB in total.

## Option B: about ₹450 a month, mostly managed

For when Oracle capacity or signup fails, or you don't want to run a server.

| Piece | Service | Cost |
| --- | --- | --- |
| web + api + scheduler + Redis | Railway Hobby (the existing `Procfile` already targets Railway) | $5 a month including $5 of usage. Check usage after week one. |
| PostgreSQL | Supabase free, Mumbai region | ₹0 (500 MB, no backups, so keep the nightly `pg_dump` from Option A) |
| Everything else | Same as Option A | ₹0 + domain |

Trade-offs: Railway's nearest region is Singapore (check it is offered on Hobby), so the API sits about 60 ms further from users and from the Mumbai database; Supabase's 500 MB is enough for the first months. The upgrade path is simple: Supabase Pro or Railway Postgres when the database nears 400 MB.

## Code and config changes needed (either option)

1. **Drop Celery in production.** Run the scheduler as its own process with `manage.py run_scheduler`. Add a PostgreSQL advisory lock so a second copy exits instead of double-sweeping; sweeps and dispatch already use `SKIP LOCKED`. Update the `Procfile` and docs. Keep the Celery task for later scale-out.
2. **Option A packaging:** `api/Dockerfile`, `web/Dockerfile` (Next.js `output: "standalone"`), `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`, and an `.env.production.example` with names only, no values.
3. **Proxy trust:** set `DJANGO_TRUST_PROXY_HEADERS`, `OTP_TRUSTED_PROXY_IPS` and `SEATLOCK_CLIENT_IP_HEADER=CF-Connecting-IP` so OTP rate limits see real client IPs through Cloudflare and Caddy.
4. **Heartbeat:** have the scheduler ping a `HEALTHCHECK_PING_URL` after each tick, so a stopped scheduler raises an alert within minutes.
5. **Error tracking:** `sentry-sdk` for Django and `@sentry/nextjs`. These are new dependencies and need approval, with PII scrubbing (phone numbers, UPI IDs).
6. **Backups:** a nightly GitHub Actions or VM cron job that runs `pg_dump`, encrypts it (age or gpg), uploads it to R2, keeps 14 dailies and 8 weeklies, and is restore-tested monthly on a scratch database.
7. **Email:** point the existing SMTP settings at Brevo and set SPF, DKIM and DMARC on the domain.

## Order of work

1. Owner approves the option and the services. Buy the domain.
2. Make the code changes above. Run the full suite on PostgreSQL in CI (currently a release gate).
3. Provision staging first (same VM, separate compose project and database). Run the guarded load stages in `api/loadtest` and the PostgreSQL race tests.
4. Put production behind Cloudflare. Bootstrap the admin. Verify TextBee OTP on real handsets. Test a backup restore.
5. Launch to a closed group from one WhatsApp community, then widen.

## Monthly cost summary

| | Option A | Option B |
| --- | --- | --- |
| Hosting | ₹0 | about ₹450 ($5) |
| Domain | about ₹50 to ₹75 (yearly ÷ 12) | same |
| Everything else | ₹0 within free limits | ₹0 |
