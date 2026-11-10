from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.events.outbox import TOPICS

RETENTION_MS = str(7 * 24 * 3600 * 1000)


class Command(BaseCommand):
    help = "Create the Seat Lock topics if missing (3 partitions, 7 day retention). Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--partitions", type=int, default=3)
        parser.add_argument("--replication-factor", type=int, default=1)

    def handle(self, *args, partitions=3, replication_factor=1, **options):
        if not settings.KAFKA_ENABLED:
            raise CommandError("KAFKA_ENABLED is off.")
        from confluent_kafka import KafkaException
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
        existing = set(admin.list_topics(timeout=10).topics)
        wanted = [NewTopic(t, num_partitions=partitions, replication_factor=replication_factor,
                           config={"retention.ms": RETENTION_MS, "cleanup.policy": "delete"})
                  for t in TOPICS if t not in existing]
        for topic, future in admin.create_topics(wanted).items() if wanted else []:
            try:
                future.result()
                self.stdout.write(f"created {topic}")
            except KafkaException as exc:
                raise CommandError(f"Could not create {topic}: {exc}") from None
        for topic in TOPICS:
            if topic in existing:
                self.stdout.write(f"exists {topic}")
