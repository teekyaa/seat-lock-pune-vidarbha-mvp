import time

from django.core.management.base import BaseCommand

from apps.notifications.tasks import run_tick


class Command(BaseCommand):
    help = "Run the per-minute scheduler tick in a loop without Celery or Redis (local development)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run a single tick and exit.")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, once=False, interval=60, **options):
        while True:
            result = run_tick()
            self.stdout.write(str(result))
            if once:
                return
            time.sleep(interval)
