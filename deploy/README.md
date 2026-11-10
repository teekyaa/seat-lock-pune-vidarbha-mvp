# Deploying Seat Lock on one Oracle Always Free VM

Option A from `docs/DEPLOYMENT_FREE_TIER.md`. Everything runs in Docker on one Ampere (arm64) VM behind Cloudflare:

```text
Cloudflare ── Caddy :443 ─┬─ web (Next.js) ── api (Django, gunicorn) ─┬─ db (PostgreSQL 16)
                          └─ /admin /static /healthz /readyz → api      ├─ redis (cache, rate limits)
             scheduler (one tick loop, advisory lock) ──────────────────┤
             relay (outbox → Kafka) ── kafka (KRaft, single node) ── consumer-metrics (Kafka → DB)
```

Only Caddy publishes ports. Why Kafka is here and how events flow: `docs/EVENTS_KAFKA.md`.

## 1. Create the VM

1. Sign up at Oracle Cloud with **home region Mumbai or Hyderabad**. The region can't be changed later.
2. Upgrade the account to **Pay As You Go**, which needs a card. You aren't charged within Always Free limits, and PAYG VMs aren't reclaimed as idle. Set a budget alert at ₹1.
3. Create an instance:
   - Shape **VM.Standard.A1.Flex** with **2 OCPU / 12 GB**.
   - Image **Ubuntu 24.04 (aarch64)**, boot volume 100 GB.
   - Add your SSH public key.
   - If you get "Out of host capacity", retry later or try another availability domain.
4. In the subnet's security list, allow inbound **TCP 22 from your IP only**, and **TCP 80/443 from Cloudflare ranges only** (https://www.cloudflare.com/ips/). Ubuntu images on Oracle also ship iptables rules, so open 80/443 there too, or use `ufw` with the same sources.

## 2. Prepare the server

```bash
sudo apt update && sudo apt -y upgrade && sudo apt -y install docker.io docker-compose-v2 git gpg rclone unattended-upgrades
```
```bash
sudo usermod -aG docker $USER && newgrp docker
```
```bash
sudo git clone https://github.com/teekyaa/seat-lock-pune-vidarbha-mvp.git /opt/seatlock && sudo chown -R $USER /opt/seatlock
```

## 3. Domain and certificates

1. Buy the domain, add it to Cloudflare (free plan), and create an **A record** to the VM's public IP with the proxy (orange cloud) **on**.
2. Under SSL/TLS, set the mode to **Full (strict)**. Then go to Origin Server, **Create certificate** (15 years), and save the files as `deploy/certs/origin.pem` and `deploy/certs/origin-key.pem` (`chmod 600`).
3. Turn on Always Use HTTPS. Add one free **rate limiting rule** for `/api/proxy/auth/otp/request` (for example 20 requests per minute per IP) as a first line of defence in front of the app's own OTP limits.

## 4. Configure

```bash
cd /opt/seatlock/deploy && cp .env.production.example .env && chmod 600 .env
```

Fill in every value in `.env`:
- **Passwords:** `openssl rand -hex 32` for each one.
- **`DJANGO_SECRET_KEY`:** `openssl rand -hex 50`.
- **`KAFKA_CLUSTER_ID`:**
  ```bash
  docker run --rm apache/kafka:3.9.1 /opt/kafka/bin/kafka-storage.sh random-uuid
  ```
- **`ADMIN_TOTP_ENCRYPTION_KEY`:**
  ```bash
  docker run --rm python:3.12-slim sh -c "pip -q install cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
  ```

Keep a copy of `.env` in your password manager. Losing `ADMIN_TOTP_ENCRYPTION_KEY` locks out every admin, and losing `BACKUP_PASSPHRASE` makes every backup unreadable.

## 5. First start

```bash
docker compose up -d --build db redis kafka
```
```bash
docker compose run --rm api python manage.py migrate
```
```bash
docker compose run --rm api python manage.py seed_reference_data
```
```bash
docker compose run --rm api python manage.py create_event_topics
```
```bash
docker compose up -d --build
```
```bash
docker compose run --rm api python manage.py bootstrap_admin --email you@example.com --name "Your Name"
```

Check that `https://<domain>/readyz` returns `{"ready": true}` and that `docker compose ps` shows every service running.

## 6. Deploying a new version

```bash
cd /opt/seatlock && git pull && cd deploy && docker compose build
```
```bash
docker compose run --rm api python manage.py migrate
```
```bash
docker compose up -d
```

Migrations run before the new containers start. Review each migration for compatibility with the running version first (see `docs/DEPLOYMENT_READINESS.md`, Rollback).

## 7. Backups

```bash
rclone config
```

Create a remote named `r2` of type S3, with provider Cloudflare, an R2 access key and the account endpoint. Then:
```bash
chmod +x /opt/seatlock/deploy/backup.sh && /opt/seatlock/deploy/backup.sh
```
```bash
(crontab -l 2>/dev/null; echo "15 21 * * * /opt/seatlock/deploy/backup.sh >> /var/log/seatlock-backup.log 2>&1") | crontab -
```

Once a month, **test a restore** into a scratch database:
```bash
rclone copy r2:seatlock-backups/daily/<file> /tmp/ && gpg -d /tmp/<file> | gunzip > /tmp/seatlock.dump
```
```bash
docker compose exec -T db createdb -U seatlock restore_test && docker compose exec -T db pg_restore -U seatlock -d restore_test < /tmp/seatlock.dump
```

## 8. Watching it

- **Uptime:** UptimeRobot on `https://<domain>/readyz` and `https://<domain>/login`.
- **Logs:** `docker compose logs -f api scheduler relay consumer-metrics`.
- **Event backlog:** Django admin, **Events > Outbox events**, filtered to unpublished. A growing backlog means the relay or Kafka is down. Bookings keep working; events catch up once it's back.
- **Kafka topics and lag:**
  ```bash
  docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group seatlock-metrics
  ```
- **Memory:** `docker stats --no-stream`. Limits in `docker-compose.yml` total about 6.2 GB of the 12 GB.
