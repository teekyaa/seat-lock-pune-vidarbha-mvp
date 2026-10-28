"""Public reliability record as a materialised view over reliability events.

Reversed events (a correction or a resolved refund points at them) are left out.
PostgreSQL gets a MATERIALIZED VIEW refreshed by the scheduler tick; SQLite (local
runs only) gets a plain VIEW so it is always current.
"""
from django.db import migrations

SELECT = """
SELECT e.user_id AS user_id,
  SUM(CASE WHEN e.kind = 'trip_completed' THEN 1 ELSE 0 END) AS completed_trips,
  SUM(CASE WHEN e.kind = 'passenger_early_cancel' THEN 1 ELSE 0 END) AS passenger_early_cancellations,
  SUM(CASE WHEN e.kind = 'passenger_late_cancel' THEN 1 ELSE 0 END) AS passenger_late_cancellations,
  SUM(CASE WHEN e.kind = 'driver_early_cancel' THEN 1 ELSE 0 END) AS driver_early_cancellations,
  SUM(CASE WHEN e.kind = 'driver_late_cancel' THEN 1 ELSE 0 END) AS driver_late_cancellations,
  SUM(CASE WHEN e.kind = 'driver_change' THEN 1 ELSE 0 END) AS driver_changes,
  SUM(CASE WHEN e.kind = 'no_show' THEN 1 ELSE 0 END) AS no_shows,
  SUM(CASE WHEN e.kind = 'refund_overdue' THEN 1 ELSE 0 END) AS open_refund_disputes
FROM trust_reliabilityevent e
WHERE e.kind NOT IN ('correction', 'refund_resolved')
  AND NOT EXISTS (SELECT 1 FROM trust_reliabilityevent r WHERE r.reverses_id = e.id)
GROUP BY e.user_id
"""


def create_view(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"CREATE MATERIALIZED VIEW trust_reliability_record AS {SELECT}")
        schema_editor.execute("CREATE UNIQUE INDEX trust_reliability_record_user ON trust_reliability_record (user_id)")
    else:
        schema_editor.execute(f"CREATE VIEW trust_reliability_record AS {SELECT}")


def drop_view(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP MATERIALIZED VIEW IF EXISTS trust_reliability_record")
    else:
        schema_editor.execute("DROP VIEW IF EXISTS trust_reliability_record")


class Migration(migrations.Migration):
    dependencies = [("trust", "0001_initial")]
    operations = [migrations.RunPython(create_view, drop_view)]
