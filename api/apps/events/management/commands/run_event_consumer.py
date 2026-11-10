import logging
import signal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.events.consumers import PoisonMessage, apply_metrics, consumer_config, parse, subscribed_topics

log = logging.getLogger(__name__)
HANDLERS = {"metrics": apply_metrics}


class Command(BaseCommand):
    help = "Consume domain events from Kafka and apply one consumer's effect (default: metrics)."

    def add_arguments(self, parser):
        parser.add_argument("--consumer", default="metrics", choices=sorted(HANDLERS))
        parser.add_argument("--max-messages", type=int, default=0, help="Stop after this many (0 = forever).")
        parser.add_argument("--idle-timeout", type=float, default=0,
                            help="Stop after this many seconds without messages (0 = never). For tests.")

    def handle(self, *args, consumer="metrics", max_messages=0, idle_timeout=0, **options):
        if not settings.KAFKA_ENABLED:
            raise CommandError("KAFKA_ENABLED is off; nothing to consume.")
        from confluent_kafka import Consumer, KafkaException

        handler = HANDLERS[consumer]
        kafka = Consumer(consumer_config(f"seatlock-{consumer}"))
        kafka.subscribe(subscribed_topics())
        stopping = []
        signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
        handled = idle = 0
        self.stdout.write(f"Consumer '{consumer}' started.")
        try:
            while not stopping and (not max_messages or handled < max_messages):
                msg = kafka.poll(1.0)
                if msg is None:
                    idle += 1
                    if idle_timeout and idle >= idle_timeout:
                        break
                    continue
                idle = 0
                if msg.error():
                    if msg.error().fatal():
                        raise KafkaException(msg.error())
                    continue  # e.g. partition EOF or a transient broker error
                close_old_connections()
                try:
                    applied = handler(parse(msg.value()), consumer)
                except PoisonMessage as exc:
                    # Never block the partition on a message that can never succeed.
                    log.error("Skipping bad event at %s[%s]@%s: %s", msg.topic(), msg.partition(), msg.offset(), exc)
                    applied = False
                # The DB transaction has committed by now; only then move the group's position.
                kafka.commit(message=msg, asynchronous=False)
                handled += 1
                if applied:
                    self.stdout.write(f"applied {msg.topic()}[{msg.partition()}]@{msg.offset()}")
        finally:
            kafka.close()
        self.stdout.write(f"Consumer '{consumer}' stopped after {handled} messages.")
