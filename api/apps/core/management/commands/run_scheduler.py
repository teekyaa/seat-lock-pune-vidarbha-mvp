import signal
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.notifications.tasks import run_tick

# Any constant works; it only has to be the same in every scheduler process.
SCHEDULER_LOCK_KEY = 5_172_026


def holds_scheduler_lock():
    """True if this process holds the scheduler lock (PostgreSQL), or on SQLite where there is one process.

    pg_try_advisory_lock is re-entrant within a session, so calling it every tick is safe. If the
    database connection dropped and reconnected, the lock was released with it; if another scheduler
    took it meanwhile, this returns False and this process stops.
    """
    if connection.vendor != "postgresql":
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SCHEDULER_LOCK_KEY])
        return bool(cursor.fetchone()[0])


class Command(BaseCommand):
    help = ("Run the per-minute scheduler tick (sweeps, notifications, reliability view, outbox pruning). "
            "Production runs exactly one; a second copy exits because it cannot take the advisory lock.")

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run a single tick and exit.")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, once=False, interval=60, **options):
        stopping = []
        signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
        while not stopping:
            if not holds_scheduler_lock():
                raise CommandError("Another scheduler holds the lock; exiting so ticks never run twice.")
            started = time.monotonic()
            result = run_tick()
            self.stdout.write(str(result))
            if once:
                return
            # Sleep in short steps so SIGTERM stops the loop promptly.
            while not stopping and time.monotonic() - started < interval:
                time.sleep(1)
