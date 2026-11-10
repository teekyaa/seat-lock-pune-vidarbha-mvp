"""Only one scheduler may run ticks. PostgreSQL advisory lock; SQLite has a single process anyway."""
import threading

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections

from apps.core.management.commands.run_scheduler import SCHEDULER_LOCK_KEY, holds_scheduler_lock


@pytest.mark.django_db
def test_sqlite_always_holds_the_lock():
    if connection.vendor == "postgresql":
        pytest.skip("SQLite behaviour")
    assert holds_scheduler_lock() is True


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="advisory locks need PostgreSQL")
def test_second_scheduler_cannot_take_the_lock():
    assert holds_scheduler_lock() is True
    assert holds_scheduler_lock() is True  # re-entrant for the holder, so checking every tick is safe
    result = {}

    def other_process():
        try:
            result["holds"] = holds_scheduler_lock()
            with pytest.raises(CommandError):
                call_command("run_scheduler", "--once")
            result["refused"] = True
        finally:
            connections.close_all()

    thread = threading.Thread(target=other_process)  # its own DB connection, like another container
    thread.start()
    thread.join()
    assert result == {"holds": False, "refused": True}
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock_all()")
    assert SCHEDULER_LOCK_KEY
