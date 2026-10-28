from celery import shared_task
from django.utils import timezone

from apps.bookings import sweeps
from apps.trust.services import refresh_reliability_view

from .dispatch import dispatch_due


def run_tick(now=None):
    """One scheduler pass: state sweeps, then due notifications, then the public record."""
    now = now or timezone.now()
    result = sweeps.run_all(now)
    result["notifications"] = dispatch_due(now)
    refresh_reliability_view()
    return result


@shared_task(name="apps.notifications.tasks.tick", ignore_result=True)
def tick():
    return run_tick()
