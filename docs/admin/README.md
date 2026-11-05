# Admin dashboard development

The dashboard is an **incomplete development foundation**. It must not be deployed as a production-ready operations console. Discovery, decisions, outstanding requirements and security gates are recorded in `DISCOVERY.md`, `../DECISIONS.md`, `BACKLOG.md` and `PRODUCTION_READINESS.md`. The currently implemented controls and their limits are in `RUNBOOK.md`.

## Separate admin setup

No rider/driver login grants admin access. Set a dedicated `ADMIN_TOTP_ENCRYPTION_KEY` environment variable to a valid Fernet key. Keep it in a local ignored `api/.env` for development or a secret manager for production; never paste it into chat or source control. Protect and back up the key separately from the database. A lost key makes existing TOTP secrets unreadable; a reviewed recovery and rotation procedure is still required.

To generate a local encryption key without displaying it, run in PowerShell from `api/` and add it **only once** to an existing ignored `.env` file:

```powershell
if (Select-String -LiteralPath .env -Pattern '^ADMIN_TOTP_ENCRYPTION_KEY=' -Quiet) { throw 'Admin key is already configured; do not replace it.' }
$adminKey = .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; import sys; sys.stdout.write(Fernet.generate_key().decode())"
Add-Content -LiteralPath .env -Value ("`nADMIN_TOTP_ENCRYPTION_KEY=" + $adminKey)
Remove-Variable adminKey
```

Restart Django after changing `.env`. Run migrations, then from an access-controlled terminal run `python manage.py bootstrap_admin --email YOUR_ADMIN_EMAIL --name YOUR_NAME`. The command prompts without echo for a password and a base32 authenticator setup key and verifies a current six-digit code. Generate the setup key from at least 20 cryptographically random bytes using a trusted authenticator or password manager; do not use a memorized phrase. Retain it securely for the setup process and do not send the key, password or code to chat. The command permits only the first administrator and consumes the initial TOTP counter; wait for the next code to sign in. Account creation by an existing super admin and account recovery are not implemented.

Visit `/control/login`. The separate admin cookie is httpOnly, SameSite Strict and secure in production. Server-side sessions expire after 30 minutes of inactivity and 12 hours absolute; the 30-second overview polling does not extend idle time. In production the admin API is disabled unless `ADMIN_DASHBOARD_ENABLED=1` and a valid encryption key is present. An actual deployment must verify HTTPS and origin handling behind its trusted proxy.

## Schema and tests

From `api/`, regenerate the scoped schema with `python manage.py spectacular --urlconf apps.admin_dashboard.schema_urls --file ../docs/admin/openapi.yaml --validate`. From `web/`, run `npx openapi-typescript ../docs/admin/openapi.yaml -o src/lib/admin-api.generated.ts`. Do not edit generated files by hand.

Run backend tests with `python -m pytest`; frontend lint with `npm run lint`; TypeScript with `npx tsc --noEmit`; and browser checks with `npx playwright test` against the configured local server. On Windows, `api/tests/run_admin_browser_e2e.ps1` runs the synthetic TOTP login, control change and logout journey on dedicated local ports with a disposable SQLite database and no SMS. PostgreSQL-only tests require an isolated PostgreSQL instance. Component tests, a full admin end-to-end suite, coverage enforcement, complete seed data and the requested Makefile targets remain incomplete.
