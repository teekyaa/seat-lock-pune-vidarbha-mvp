#!/usr/bin/env bash
# Nightly encrypted PostgreSQL backup to Cloudflare R2 (or any rclone remote).
# Run from cron on the VM:  15 21 * * *  /opt/seatlock/deploy/backup.sh >> /var/log/seatlock-backup.log 2>&1
# (21:15 UTC is 02:45 IST.) Needs: docker, gpg, rclone configured with a remote named in RCLONE_REMOTE.
# Kafka is not backed up: the outbox and the database are the source of truth, and consumers rebuild.
set -euo pipefail

cd "$(dirname "$0")"
# Read only what this script needs; .env has values with spaces that a shell cannot source.
env_value() { grep -E "^$1=" .env | tail -n 1 | cut -d= -f2-; }
BACKUP_PASSPHRASE="$(env_value BACKUP_PASSPHRASE)"
RCLONE_REMOTE="$(env_value RCLONE_REMOTE)"
: "${BACKUP_PASSPHRASE:?set BACKUP_PASSPHRASE in deploy/.env}"
: "${RCLONE_REMOTE:?set RCLONE_REMOTE in deploy/.env}"

stamp="$(date -u +%Y-%m-%dT%H%MZ)"
kind="daily"; [ "$(date -u +%u)" = "7" ] && kind="weekly"
file="/tmp/seatlock-${kind}-${stamp}.sql.gz.gpg"
trap 'rm -f "$file"' EXIT

# Custom-format dumps restore selectively; gzip on top keeps the upload small.
docker compose exec -T db pg_dump -U seatlock -d seatlock --format=custom --no-owner \
  | gzip -9 \
  | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$BACKUP_PASSPHRASE" -o "$file"

[ -s "$file" ] || { echo "backup is empty, refusing to upload" >&2; exit 1; }
rclone copy "$file" "${RCLONE_REMOTE}/${kind}/" --s3-no-check-bucket
echo "uploaded $(basename "$file") ($(du -h "$file" | cut -f1))"

# Keep 14 daily and 8 weekly backups.
rclone delete "${RCLONE_REMOTE}/daily/" --min-age 14d
rclone delete "${RCLONE_REMOTE}/weekly/" --min-age 56d
