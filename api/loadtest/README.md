# Isolated load and concurrency tests

These tests create users, rides, bookings and notifications. Run only against a disposable environment with synthetic data. They do not request OTPs or call TextBee. No load-test results are supplied by this repository.

1. Create a dedicated PostgreSQL database named exactly `seatlock_loadtest`, with a test role allowed to create Django's temporary test database. Configure at least 110 database connections for the 100-thread race, plus headroom for other services. Create a separate Redis instance/database. Never point these variables at a live environment.
2. In a dedicated API environment, set `DJANGO_DEBUG=1`, a test `DJANGO_SECRET_KEY`, `DATABASE_URL` for that database, an isolated `REDIS_URL`, `SEATLOCK_LOADTEST_MODE=yes`, `SMS_BACKEND=apps.notifications.channels.UnconfiguredSMSBackend`, and empty `TEXTBEE_API_KEY`/`TEXTBEE_DEVICE_ID`. Migrate and run `python manage.py seed_loadtest --confirm-isolated --users 500`. This writes bearer tokens to ignored `api/.loadtest/accounts.json`; protect and delete that file after use. Run the API on the isolated network with a production-like app server and worker configuration, not Django's development server.
3. Install `locust==2.47.0` in a separate load-generator environment. Set `SEATLOCK_LOADTEST_ISOLATED=yes` and `SEATLOCK_LOADTEST_HOST` to the isolated API URL. The script checks an endpoint that is available only when the API uses debug mode, the explicit test flag and the named PostgreSQL database. Run from `api/`:

   ```sh
   locust -f loadtest/locustfile.py --headless --host "$SEATLOCK_LOADTEST_HOST" -u 50 -r 5 -t 5m --csv loadtest-50
   locust -f loadtest/locustfile.py --headless --host "$SEATLOCK_LOADTEST_HOST" -u 100 -r 5 -t 5m --csv loadtest-100
   locust -f loadtest/locustfile.py --headless --host "$SEATLOCK_LOADTEST_HOST" -u 250 -r 5 -t 10m --csv loadtest-250
   locust -f loadtest/locustfile.py --headless --host "$SEATLOCK_LOADTEST_HOST" -u 500 -r 2 -t 35m --csv loadtest-500
   ```

   The 500-user run allows just over 30 minutes after ramp-up. The workload uses pre-authenticated synthetic users: browse, search, profile, ride details, create and update rides, and request/cancel bookings. HTTP 409 booking conflicts count as expected; instrument their codes separately before interpreting a capacity result because Locust's aggregate success count includes them. The test does not measure the login/OTP endpoint or SMS throughput. Distributed Locust workers each need their own disjoint accounts to avoid identity reuse; this script is intended for one generator process.
4. Record RPS, mean/p95/p99 latency, unexpected error rates, number of active users over time, host CPU and memory, PostgreSQL active/idle connections, and query timings (for example via `pg_stat_statements`). Check database seat counts, constraint failures, worker crashes and memory over time. Capture generator CPU too; a saturated generator invalidates the result. Run the API and generator on separate sized machines for a capacity claim.
5. For the separate 100-way database race, configure `DATABASE_URL` to the isolated PostgreSQL instance and run `pytest tests/test_concurrency.py -m stress`. That test needs at least 110 available connections. The regular CI run deliberately excludes this expensive test.

Do not paste generated tokens into reports. Store aggregated result CSVs separately; they may contain request paths and operational metadata.
