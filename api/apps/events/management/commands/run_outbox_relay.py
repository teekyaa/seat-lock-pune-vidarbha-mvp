import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.events.relay import KafkaProducerAdapter, publish_batch


class Command(BaseCommand):
    help = "Publish outbox events to Kafka in a loop (one relay process per deployment is enough)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Publish one batch and exit.")
        parser.add_argument("--idle-sleep", type=float, default=1.0)

    def handle(self, *args, once=False, idle_sleep=1.0, **options):
        if not settings.KAFKA_ENABLED:
            raise CommandError("KAFKA_ENABLED is off; nothing to relay.")
        producer = KafkaProducerAdapter()
        stopping = []
        signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
        self.stdout.write("Outbox relay started.")
        while not stopping:
            close_old_connections()
            try:
                published, failed = publish_batch(producer)
            except Exception as exc:  # keep the relay alive through DB or broker blips
                self.stderr.write(f"Relay batch failed: {type(exc).__name__}")
                published, failed = 0, 1
            if published or failed:
                self.stdout.write(f"published={published} failed={failed}")
            if once:
                return
            if not published:
                time.sleep(idle_sleep)  # a full batch means more may be waiting; loop straight away
        self.stdout.write("Outbox relay stopped.")
