from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_tripshare"),
        ("rides", "0002_ride_codriver_wanted"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="role",
            field=models.CharField(choices=[("passenger", "Passenger"), ("co_driver", "Co-driver")], default="passenger", max_length=12),
        ),
        migrations.AddField(
            model_name="booking",
            name="co_driver_license_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="role",
            field=models.CharField(choices=[("passenger", "Passenger"), ("co_driver", "Co-driver")], default="passenger", max_length=12),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="co_driver_license_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(condition=models.Q(("role", "co_driver"), ("status__in", ["requested", "accepted", "advance_claimed", "confirmed"])), fields=("ride",), name="one_active_codriver_per_ride"),
        ),
    ]
